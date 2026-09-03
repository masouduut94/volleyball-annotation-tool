"""
Lightweight wrapper around a locally-checkpointed VideoMAE model for
volleyball game-state classification (service / play / no-play).

Everything VideoMAE-specific lives in this one file on purpose — swap this
out if you want a different backbone later; nothing else in the app should
need to know it's VideoMAE.
"""
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import cv2
import torch
from transformers import VideoMAEImageProcessor, VideoMAEForVideoClassification

VALID_STATES = {"service", "play", "no-play"}


@dataclass
class GameStateResult:
    state: str        # "service" | "play" | "no-play" | "unknown"
    confidence: float


class GameStateClassifier:
    def __init__(self, num_frames: int = 16, resize_to: int = 224, device: Optional[str] = None):
        self.model_path: Optional[str] = None
        self.processor = None
        self.model = None
        self.num_frames = num_frames
        self.resize_to = resize_to
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    # ------------------------------------------------------------------
    # Lifecycle — mirrors AutoAnnotator's is_configured/ensure_loaded
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        return self.model is not None

    def ensure_loaded(self, model_path: str) -> bool:
        if not model_path:
            return False

        if self.model is not None and self.model_path == model_path:
            return True

        try:
            self.processor = VideoMAEImageProcessor.from_pretrained(model_path)
            self.model = VideoMAEForVideoClassification.from_pretrained(
                model_path, dtype=torch.float16
            )
            self.model.to(self.device)
            self.model.eval()
            self.model_path = model_path
            return True
        except Exception:
            self.processor = None
            self.model = None
            self.model_path = None
            return False

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _prepare(self, frames: List[np.ndarray]):
        rgb = [
            cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2RGB), (self.resize_to, self.resize_to))
            for f in frames
            if f is not None
        ]

        # Uniform temporal subsample down to num_frames if the caller
        # handed us a bigger window than the model expects.
        if len(rgb) > self.num_frames:
            step = (len(rgb) - 1) / (self.num_frames - 1)
            rgb = [rgb[min(int(round(i * step)), len(rgb) - 1)] for i in range(self.num_frames)]

        inputs = self.processor(rgb, return_tensors="pt")
        return {k: v.to(self.device).half() for k, v in inputs.items()}

    def classify(self, frames: List[np.ndarray]) -> GameStateResult:
        if self.model is None:
            raise RuntimeError("Game-state model is not loaded. Set a model path first.")

        if not frames:
            return GameStateResult(state="unknown", confidence=0.0)

        inputs = self._prepare(frames)

        with torch.no_grad():
            logits = self.model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)
        idx = int(torch.argmax(probs, dim=-1).item())
        confidence = float(probs[0][idx].item())
        label = self.model.config.id2label[idx].lower()

        state = label if label in VALID_STATES else "unknown"
        return GameStateResult(state=state, confidence=confidence)