"""
Game-state classifier (service / play / no-play) for checkpoints produced by
train_videomae_unified.py (v1 = HF VideoMAE, v2 = custom backbone + linear head).

Public surface is a superset of the old transformers-only wrapper, so
MainWindow / GameStateWorker keep working:

    is_configured()                  -> bool
    ensure_loaded(path)              -> bool   (path is now a single .pt file)
    frame_indices(n)                 -> the exact frame positions (0..n-1) the
                                        model looks at for a window of n frames
    classify(frames)                 -> GameStateResult         (one window)
    classify_batch(windows, bs)      -> list[GameStateResult]   (many windows)

Everything checkpoint/backbone specific lives in this file only.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision.transforms import v2 as T
from transformers import AutoConfig, AutoModel, VideoMAEForVideoClassification

# States the rest of the app understands.
VALID_STATES = {"service", "play", "no-play"}
# Checkpoint class name -> app state. The model predicts
# [in_play, no_play, service]. Lookup keys are normalised first (lower-case,
# "-" and spaces -> "_"), so "In-Play", "in play" and "in_play" all match.
# Edit this dict if you train with different class names.
LABEL_TO_STATE = {
    "service": "service",
    "serve": "service",
    "in_play": "play",
    "inplay": "play",
    "play": "play",
    "active_play": "play",
    "no_play": "no-play",
    "noplay": "no-play",
}

DEFAULT_CLASSES = ["in_play", "no_play", "service"]
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass
class GameStateResult:
    state: str  # "service" | "play" | "no-play" | "unknown"
    confidence: float  # probability of the predicted *checkpoint* class
    raw_label: str = ""  # class name exactly as stored in the checkpoint
    probs: Dict[str, float] = field(default_factory=dict)


# ============================================================================
# Model — same attribute names as the training script, so state_dict keys match
# ============================================================================
class VideoMAEClassifier(nn.Module):
    """forward(x): x is (B, T, C, H, W) -> logits (B, num_classes)."""

    def __init__(self, version, model_name, classes, num_frames=16,
                 image_size=224, feat_dim=None):
        super().__init__()
        if version not in (1, 2):
            raise ValueError(f"Unsupported checkpoint version: {version}")

        self.version = version
        self.num_frames = num_frames
        self.image_size = image_size
        num_classes = len(classes)

        # NOTE: we build from the *config* only (no pretrained weights are
        # downloaded) because the fine-tuned state_dict overwrites everything
        # right after. The config itself comes from the HF cache / hub.
        if version == 1:
            config = AutoConfig.from_pretrained(
                model_name,
                num_labels=num_classes,
                id2label=dict(enumerate(classes)),
                label2id={c: i for i, c in enumerate(classes)},
            )
            self.model = VideoMAEForVideoClassification(config)
            self.num_frames = config.num_frames
            self.image_size = config.image_size
        else:
            config = AutoConfig.from_pretrained(model_name, trust_remote_code=True)
            self.backbone = AutoModel.from_config(config, trust_remote_code=True)
            if hasattr(self.backbone, "head"):
                self.backbone.head = nn.Identity()
            if feat_dim is None:
                self.backbone.eval()
                with torch.no_grad():
                    feat_dim = self.backbone(
                        torch.zeros(1, 3, num_frames, image_size, image_size)
                    ).shape[-1]
            self.head = nn.Sequential(nn.Dropout(0.0), nn.Linear(feat_dim, num_classes))

    def forward(self, x):
        if self.version == 1:
            return self.model(pixel_values=x).logits
        return self.head(self.backbone(x.permute(0, 2, 1, 3, 4)))


# ============================================================================
# Sampling / preprocessing (identical to validation in the training script)
# ============================================================================
def sample_indices(n_avail: int, num_frames: int) -> List[int]:
    """Segment-centre sampling: split n_avail frames into num_frames equal
    segments and take the middle frame of each (duplicates if n_avail is
    smaller than num_frames)."""
    seg = n_avail / num_frames
    return [min(max(int(seg * i + seg / 2), 0), n_avail - 1) for i in range(num_frames)]


class Preprocessor:
    def __init__(self, num_frames, image_size, mean, std):
        self.num_frames = num_frames
        short = int(image_size * 256 / 224)
        self.tf = T.Compose([T.Resize(short, antialias=True), T.CenterCrop(image_size)])
        self.mean = torch.tensor(mean, dtype=torch.float32).view(1, 3, 1, 1)
        self.std = torch.tensor(std, dtype=torch.float32).view(1, 3, 1, 1)

    def __call__(self, frames_bgr: Sequence[np.ndarray]) -> torch.Tensor:
        """list of BGR uint8 frames -> (T, C, H, W) normalised float tensor."""
        idx = sample_indices(len(frames_bgr), self.num_frames)
        clip = np.stack([cv2.cvtColor(frames_bgr[i], cv2.COLOR_BGR2RGB) for i in idx])
        clip = torch.from_numpy(clip).permute(0, 3, 1, 2)  # T,C,H,W uint8
        clip = self.tf(clip).float() / 255.0
        return (clip - self.mean) / self.std


# ============================================================================
# Public wrapper
# ============================================================================
class GameStateClassifier:
    def __init__(self, device: Optional[str] = None, use_fp16: bool = True):
        self.model_path: Optional[str] = None
        self.model: Optional[VideoMAEClassifier] = None
        self.pre: Optional[Preprocessor] = None
        self.classes: List[str] = []
        self.last_error: Optional[str] = None  # why the last ensure_loaded() failed

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.use_fp16 = use_fp16

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def num_frames(self) -> int:
        return self.model.num_frames if self.model is not None else 16

    def is_configured(self) -> bool:
        return self.model is not None

    def ensure_loaded(self, model_path: str) -> bool:
        if not model_path:
            return False
        if self.model is not None and self.model_path == model_path:
            return True

        try:
            ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
            for key in ("version", "model_name", "state_dict"):
                if key not in ckpt:
                    raise KeyError(f"checkpoint is missing '{key}'")

            classes = list(ckpt.get("classes", DEFAULT_CLASSES))
            state_dict = ckpt["state_dict"]

            feat_dim = None
            if ckpt["version"] == 2 and "head.1.weight" in state_dict:
                feat_dim = state_dict["head.1.weight"].shape[1]

            model = VideoMAEClassifier(
                ckpt["version"], ckpt["model_name"], classes,
                ckpt.get("num_frames", 16), ckpt.get("image_size", 224),
                feat_dim=feat_dim,
            )
            model.load_state_dict(state_dict)
            model.to(self.device).eval()

            self._release()
            self.model = model
            self.classes = classes
            self.pre = Preprocessor(
                model.num_frames, model.image_size,
                ckpt.get("mean", IMAGENET_MEAN), ckpt.get("std", IMAGENET_STD),
            )
            self.model_path = model_path
            self.last_error = None
            return True

        except Exception as e:
            self._release()
            self.last_error = f"{type(e).__name__}: {e}"
            return False

    def _release(self):
        self.model = None
        self.pre = None
        self.classes = []
        self.model_path = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def frame_indices(self, n_frames: int) -> List[int]:
        """Positions (0..n_frames-1) inside a window that the model actually
        uses. Lets a caller decode ONLY those frames instead of the whole
        window (saves RAM and decode time)."""
        return sample_indices(n_frames, self.num_frames)

    def _to_result(self, probs: np.ndarray) -> GameStateResult:
        k = int(probs.argmax())
        raw = self.classes[k]
        key = raw.lower().strip().replace("-", "_").replace(" ", "_")
        state = LABEL_TO_STATE.get(key, "unknown")
        return GameStateResult(
            state=state,
            confidence=float(probs[k]),
            raw_label=raw,
            probs={c: float(p) for c, p in zip(self.classes, probs)},
        )

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    @torch.inference_mode()
    def classify_batch(
            self,
            windows: Sequence[Sequence[np.ndarray]],
            batch_size: int = 8,
    ) -> List[GameStateResult]:
        """
        Classify many windows. Each window is a list of BGR frames of ANY
        length (it is resampled to the model's frame count internally).
        Windows are pushed through the network `batch_size` at a time, one
        forward pass per chunk. Returns one result per input window, in order.
        """
        if self.model is None or self.pre is None:
            raise RuntimeError("Game-state model is not loaded. Set a model path first.")

        results: List[Optional[GameStateResult]] = [None] * len(windows)
        valid = []
        for i, window in enumerate(windows):
            frames = [f for f in window if f is not None]
            if frames:
                valid.append((i, frames))
            else:
                results[i] = GameStateResult(state="unknown", confidence=0.0)

        bs = max(1, int(batch_size))
        use_amp = self.use_fp16 and self.device.startswith("cuda")

        for s in range(0, len(valid), bs):
            chunk = valid[s:s + bs]
            x = torch.stack([self.pre(frames) for _, frames in chunk])
            x = x.to(self.device, non_blocking=True)

            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                logits = self.model(x)

            probs = torch.softmax(logits.float(), dim=-1).cpu().numpy()
            for (i, _), p in zip(chunk, probs):
                results[i] = self._to_result(p)

        return results

    def classify(self, frames: List[np.ndarray]) -> GameStateResult:
        """Single-window convenience wrapper (kept for backwards compatibility)."""
        return self.classify_batch([frames], batch_size=1)[0]