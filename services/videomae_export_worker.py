"""
Worker that builds a frame-clip dataset for VideoMAE game-state training
from the manually/AI-tagged game_state_segments already stored in the DB.

Sampling strategy, per your spec:
  - "service" clips are short and scarce, so EVERY stored service segment
    becomes exactly one clip — no random sampling.
  - "play" / "no-play" segments tend to be long, so instead we draw random
    windows of `clip_length` frames from anywhere inside them, repeatedly,
    until the requested clip count for that state is reached. Segments are
    weighted by their length (more frames = more chances to be picked),
    since a 10s no-play stretch should contribute more candidate windows
    than a 3s one.

Each clip is resampled to exactly `clip_length` frames via uniform
subsampling (or, for anything shorter than clip_length, uniform
duplication) — the same approach GameStateClassifier already uses at
inference time, so training and inference windows are shaped the same way.

Augmentations (if selected) are applied per-clip, consistently across all
frames of that clip: each enabled augmentation produces one extra copy of
every clip (mirrors YOLOExportDialog's augmentation semantics).

Output layout:
    output_dir/
        service/clip_0000/frame_0000.jpg ...
        play/clip_0000/frame_0000.jpg ...
        no-play/clip_0000/frame_0000.jpg ...
        manifest.csv
"""

import csv
import random
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

STATE_DIR_NAMES = {"service": "service", "play": "play", "no-play": "no-play"}


def _sample_frame_indices(start, end, clip_length):
    """
    Return exactly `clip_length` frame indices spanning [start, end].
    Uniform subsample if the range is longer than clip_length, uniform
    duplication (nearest index) if it's shorter.
    """
    span = end - start + 1
    if clip_length <= 1:
        return [start]
    if span == clip_length:
        return list(range(start, end + 1))

    step = (span - 1) / (clip_length - 1)
    return [start + min(int(round(i * step)), span - 1) for i in range(clip_length)]


def _weighted_segment_choice(segments, rng):
    """Pick one segment, weighted by its frame-length."""
    weights = [max(1, s.end_frame - s.start_frame + 1) for s in segments]
    return rng.choices(segments, weights=weights, k=1)[0]


class VideoMAEExportWorker(QObject):
    progress = pyqtSignal(int)         # 0-100
    finished = pyqtSignal(dict)        # {"service": n, "play": n, "no-play": n, "total": n}
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, db, settings, parent=None):
        super().__init__(parent)
        self.db = db
        self.settings = settings
        self._cancelled = False
        self._rng = random.Random()

    def cancel(self):
        self._cancelled = True

    # ------------------------------------------------------------
    # Augmentations — applied consistently across every frame in a clip
    # ------------------------------------------------------------

    def _aug_brightness_contrast(self, frames):
        alpha = self._rng.uniform(0.8, 1.2)   # contrast
        beta = self._rng.uniform(-25, 25)      # brightness
        return [cv2.convertScaleAbs(f, alpha=alpha, beta=beta) for f in frames]

    def _aug_horizontal_flip(self, frames):
        return [cv2.flip(f, 1) for f in frames]

    def _aug_rgb_manipulation(self, frames):
        # Per-channel gain, same gain for every frame in the clip so the
        # color shift reads as one continuous lighting/color condition
        # rather than flickering frame to frame.
        gains = np.array([self._rng.uniform(0.85, 1.15) for _ in range(3)])
        out = []
        for f in frames:
            shifted = f.astype(np.float32) * gains
            out.append(np.clip(shifted, 0, 255).astype(np.uint8))
        return out

    AUGMENTATION_FUNCS = {
        "brightness_contrast": _aug_brightness_contrast,
        "horizontal_flip": _aug_horizontal_flip,
        "rgb_manipulation": _aug_rgb_manipulation,
    }

    # ------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------

    def _build_plan(self):
        """
        Returns {"service": [...], "play": [...], "no-play": [...]} where
        each item is (video_path, start_frame, end_frame).
        """
        clip_length = self.settings["clip_length"]
        targets = {
            "service": None,   # None = "use every segment", not a target count
            "play": self.settings["play_clip_count"],
            "no-play": self.settings["no_play_clip_count"],
        }

        segments_by_state = {"service": [], "play": [], "no-play": []}
        for video_path in self.settings["videos"]:
            for seg in self.db.get_game_state_segments(video_path):
                if seg.state in segments_by_state:
                    seg.media_name = video_path  # ensure it's set for this video
                    segments_by_state[seg.state].append(seg)

        plan = {"service": [], "play": [], "no-play": []}

        # Service: every segment, one clip each.
        for seg in segments_by_state["service"]:
            plan["service"].append((seg.media_name, seg.start_frame, seg.end_frame))

        # Play / No-play: random windows, weighted by segment length.
        for state in ("play", "no-play"):
            candidates = [s for s in segments_by_state[state]
                         if (s.end_frame - s.start_frame + 1) >= 1]
            target = targets[state]

            if not candidates or not target:
                continue

            attempts = 0
            max_attempts = target * 20
            while len(plan[state]) < target and attempts < max_attempts:
                attempts += 1
                seg = _weighted_segment_choice(candidates, self._rng)
                seg_len = seg.end_frame - seg.start_frame + 1

                if seg_len <= clip_length:
                    window_start, window_end = seg.start_frame, seg.end_frame
                else:
                    latest_start = seg.end_frame - clip_length + 1
                    window_start = self._rng.randint(seg.start_frame, latest_start)
                    window_end = window_start + clip_length - 1

                plan[state].append((seg.media_name, window_start, window_end))

        return plan

    # ------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------

    def run(self):
        try:
            clip_length = self.settings["clip_length"]
            augmentations = self.settings["augmentations"]
            output_dir = Path(self.settings["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)

            plan = self._build_plan()
            total_raw_clips = sum(len(items) for items in plan.values())
            total_output_clips = total_raw_clips * (1 + len(augmentations))

            if total_output_clips == 0:
                self.error.emit(
                    "Nothing to export — no matching game-state segments were "
                    "found for the selected videos."
                )
                return

            manifest_rows = []
            counts = {"service": 0, "play": 0, "no-play": 0}
            done = 0
            caps = {}

            def get_cap(path):
                if path not in caps:
                    caps[path] = cv2.VideoCapture(path)
                return caps[path]

            for state, items in plan.items():
                dir_name = STATE_DIR_NAMES[state]
                for clip_idx, (video_path, start_frame, end_frame) in enumerate(items):
                    if self._cancelled:
                        self.cancelled.emit()
                        return

                    cap = get_cap(video_path)
                    indices = _sample_frame_indices(start_frame, end_frame, clip_length)

                    base_frames = []
                    for idx in indices:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                        ok, frame = cap.read()
                        if not ok:
                            frame = base_frames[-1].copy() if base_frames else None
                        if frame is not None:
                            base_frames.append(frame)

                    if not base_frames:
                        continue

                    variants = [("original", base_frames)]
                    for aug_key in augmentations:
                        func = self.AUGMENTATION_FUNCS.get(aug_key)
                        if func is not None:
                            variants.append((aug_key, func(self, base_frames)))

                    for variant_name, frames in variants:
                        clip_name = f"clip_{clip_idx:04d}_{variant_name}"
                        clip_dir = output_dir / dir_name / clip_name
                        clip_dir.mkdir(parents=True, exist_ok=True)

                        for f_idx, frame in enumerate(frames):
                            cv2.imwrite(str(clip_dir / f"frame_{f_idx:04d}.jpg"), frame)

                        manifest_rows.append({
                            "clip_path": str(clip_dir),
                            "state": state,
                            "source_video": video_path,
                            "start_frame": start_frame,
                            "end_frame": end_frame,
                            "augmentation": variant_name,
                        })
                        counts[state] += 1

                        done += 1
                        self.progress.emit(int(done / total_output_clips * 100))

            for cap in caps.values():
                cap.release()

            manifest_path = output_dir / "manifest.csv"
            with open(manifest_path, "w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["clip_path", "state", "source_video",
                                  "start_frame", "end_frame", "augmentation"]
                )
                writer.writeheader()
                writer.writerows(manifest_rows)

            counts["total"] = sum(counts.values())
            self.finished.emit(counts)

        except Exception as e:
            self.error.emit(str(e))