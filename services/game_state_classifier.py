"""
Lightweight wrapper around a locally-checkpointed VideoMAE model for
volleyball game-state classification (service / play / no-play).

Everything VideoMAE-specific lives in this one file on purpose — swap
this out if you want a different backbone later; nothing else in the
app should need to know it's VideoMAE.
"""

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np
import torch
from transformers import VideoMAEForVideoClassification, VideoMAEImageProcessor

VALID_STATES = {"service", "play", "no-play"}


@dataclass
class GameStateResult:
    state: str  # "service" | "play" | "no-play" | "unknown"
    confidence: float


class GameStateClassifier:
    def __init__(self, num_frames: int = 16, resize_to: int = 224, device: Optional[str] = None):
        self.model_path: Optional[str] = None
        self.processor = None
        self.model = None

        # Number of frames expected by VideoMAE.
        #
        # The input window itself can contain any number of frames
        # (e.g. 30, 50, 120, 10, 5), but _prepare() will always
        # convert it to exactly this number.
        self.num_frames = num_frames

        # Spatial resolution expected by the model.
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
            self.processor = VideoMAEImageProcessor.from_pretrained(
                model_path
            )

            self.model = VideoMAEForVideoClassification.from_pretrained(
                model_path,
                dtype=torch.float16,
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
    # Temporal sampling
    # ------------------------------------------------------------------

    def _select_frames(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        """
        Convert an arbitrary number of input frames into exactly
        self.num_frames frames.

        Examples with num_frames=16:

            30 frames  -> 16 frames
            50 frames  -> 16 frames
            120 frames -> 16 frames
            16 frames  -> 16 frames
            10 frames  -> 16 frames (oversampling)
            5 frames   -> 16 frames (oversampling)

        Uniform temporal sampling is used in both directions.

        When there are fewer input frames than required, some source
        frames will necessarily be selected more than once. This keeps
        the temporal ordering intact while guaranteeing that VideoMAE
        receives the exact temporal length expected by the checkpoint.
        """

        if not frames:
            return []

        if len(frames) == self.num_frames:
            return frames

        # Generate exactly self.num_frames positions distributed
        # uniformly over the available frames.
        #
        # Example:
        #   5 source frames -> 16 target frames
        #
        # The resulting indices may contain duplicates:
        #   [0, 0, 0, 1, 1, 1, 2, 2, ...]
        #
        # This is intentional oversampling.
        indices = np.linspace(
            0,
            len(frames) - 1,
            self.num_frames,
        ).round().astype(int)

        return [frames[int(index)] for index in indices]

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    def _prepare(self, frames: List[np.ndarray]):
        """
        Preprocess an arbitrary-length video window for VideoMAE.

        The caller should normally provide approximately one second
        of video:

            30 FPS -> ~30 frames
            50 FPS -> ~50 frames
            120 FPS -> ~120 frames

        Regardless of the input length, this method guarantees that
        exactly self.num_frames frames are passed to the processor/model.
        """

        # --------------------------------------------------------------
        # 1. Remove invalid frames and convert BGR -> RGB
        # --------------------------------------------------------------

        rgb = []

        for frame in frames:
            if frame is None:
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            frame_resized = cv2.resize(
                frame_rgb,
                (self.resize_to, self.resize_to),
            )

            rgb.append(frame_resized)

        if not rgb:
            raise ValueError(
                "No valid frames were provided for game-state classification."
            )

        # --------------------------------------------------------------
        # 2. Temporal sampling
        #
        # Always produce exactly self.num_frames frames.
        #
        # More frames  -> downsampling
        # Fewer frames -> oversampling
        # Equal frames  -> unchanged
        # --------------------------------------------------------------

        selected_frames = self._select_frames(rgb)

        if len(selected_frames) != self.num_frames:
            raise RuntimeError(
                f"Temporal sampling produced {len(selected_frames)} frames, "
                f"but VideoMAE requires {self.num_frames}."
            )

        # --------------------------------------------------------------
        # 3. VideoMAE preprocessing
        # --------------------------------------------------------------

        inputs = self.processor(
            selected_frames,
            return_tensors="pt",
        )

        # Move tensors to the selected device and use the same dtype
        # as the loaded model.
        inputs = {
            key: value.to(self.device).half()
            for key, value in inputs.items()
        }

        return inputs

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def classify(self, frames: List[np.ndarray]) -> GameStateResult:

        if self.model is None:
            raise RuntimeError(
                "Game-state model is not loaded. "
                "Set a model path first."
            )

        if not frames:
            return GameStateResult(
                state="unknown",
                confidence=0.0,
            )

        inputs = self._prepare(frames)

        # At this point, _prepare() guarantees that VideoMAE receives
        # exactly self.num_frames temporal frames.
        with torch.no_grad():
            logits = self.model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)

        idx = int(
            torch.argmax(probs, dim=-1).item()
        )

        confidence = float(
            probs[0][idx].item()
        )

        label = self.model.config.id2label[idx].lower()

        state = (
            label
            if label in VALID_STATES
            else "unknown"
        )

        return GameStateResult(
            state=state,
            confidence=confidence,
        )
