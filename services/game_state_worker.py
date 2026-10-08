import cv2
from PyQt6.QtCore import QObject, pyqtSignal

from src.vb_gui.vb_annotator.database.data import GameStateSegment


def merge_consecutive_segments(segments):
    """
    Collapse consecutive windows that share the same state into a single
    segment, so a 5-second in-play stretch classified as five 1s windows
    becomes one segment instead of five. "Consecutive" means touching or
    overlapping frame ranges (seg.start_frame <= previous.end_frame + 1) —
    windows are already in frame order coming out of the classification loop.

    Confidence on the merged segment is a length-weighted average of the
    windows it absorbed, so a long run isn't just represented by its first
    window's confidence.
    """
    if not segments:
        return []

    merged = []
    cur_start = segments[0].start_frame
    cur_end = segments[0].end_frame
    cur_state = segments[0].state
    cur_conf_weighted = segments[0].confidence * (cur_end - cur_start + 1)
    cur_len = cur_end - cur_start + 1

    def _flush():
        merged.append(
            GameStateSegment(
                media_name=segments[0].media_name,
                start_frame=cur_start,
                end_frame=cur_end,
                state=cur_state,
                confidence=cur_conf_weighted / max(cur_len, 1),
                source=segments[0].source,
            )
        )

    for seg in segments[1:]:
        if seg.state == cur_state and seg.start_frame <= cur_end + 1:
            cur_end = seg.end_frame
            seg_len = seg.end_frame - seg.start_frame + 1
            cur_conf_weighted += seg.confidence * seg_len
            cur_len += seg_len
        else:
            _flush()
            cur_start = seg.start_frame
            cur_end = seg.end_frame
            cur_state = seg.state
            cur_conf_weighted = seg.confidence * (cur_end - cur_start + 1)
            cur_len = cur_end - cur_start + 1

    _flush()
    return merged


class GameStateWorker(QObject):
    progress = pyqtSignal(int, int)  # windows_done, windows_total
    finished = pyqtSignal(int)  # segments saved (post-merge)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, db, classifier, video_path, media_type, width, height,
                 start_frame, end_frame, window_size=30, batch_size=8, parent=None):
        super().__init__(parent)
        self.db = db
        self.classifier = classifier
        self.video_path = video_path
        self.media_type = media_type
        self.width = width
        self.height = height
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.window_size = max(1, window_size)
        self.batch_size = max(1, int(batch_size))
        self._cancelled = False
        self._cap_pos = -1  # frame index the private capture will read next

    def cancel(self):
        self._cancelled = True

    # ------------------------------------------------------------------
    # Frame reading
    # ------------------------------------------------------------------

    def _read_window_frames(self, cap, ctx_start, ctx_end):
        """
        Decode ONLY the frames the classifier will actually look at inside
        [ctx_start, ctx_end]. All other frames are skipped with grab()
        (no pixel conversion), which is much cheaper than read() and keeps
        RAM at ~num_frames frames per window instead of window_size.

        Returns the sampled frames in the order the model expects, or []
        if nothing could be decoded.
        """
        n = ctx_end - ctx_start + 1
        indices = self.classifier.frame_indices(n)
        needed = set(indices)

        if self._cap_pos != ctx_start:
            cap.set(cv2.CAP_PROP_POS_FRAMES, ctx_start)

        decoded = {}
        read_count = 0
        for i in range(n):
            if i in needed:
                ok, frame = cap.read()
                if not ok:
                    break
                decoded[i] = frame
            else:
                if not cap.grab():
                    break
            read_count += 1

        self._cap_pos = ctx_start + read_count

        if not decoded:
            return []

        # If the video ended early, fall back to the nearest decoded frame.
        fallback = decoded[max(decoded)]
        return [decoded.get(i, fallback) for i in indices]

    # ------------------------------------------------------------------

    def run(self):
        # Own VideoCapture instance — don't share MainWindow's across threads.
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.error.emit(f"Could not open video: {self.video_path}")
            return

        windows = list(range(self.start_frame, self.end_frame + 1, self.window_size))
        total = len(windows)
        raw_segments = []
        self._cap_pos = -1

        try:
            for b_start in range(0, total, self.batch_size):
                if self._cancelled:
                    self.cancelled.emit()
                    return

                chunk = windows[b_start:b_start + self.batch_size]
                clips, spans = [], []

                for w_start in chunk:
                    w_end = min(w_start + self.window_size - 1, self.end_frame)

                    # A short tail window is classified using the last full
                    # window_size frames before it (same as the standalone
                    # inference script), but is still LABELLED with its own
                    # [w_start, w_end] range.
                    ctx_start = max(self.start_frame, w_end - self.window_size + 1)

                    frames = self._read_window_frames(cap, ctx_start, w_end)
                    if frames:
                        clips.append(frames)
                        spans.append((w_start, w_end))

                if clips:
                    results = self.classifier.classify_batch(
                        clips, batch_size=len(clips)
                    )
                    for (w_start, w_end), result in zip(spans, results):
                        raw_segments.append(
                            GameStateSegment(
                                media_name=self.video_path,
                                start_frame=w_start,
                                end_frame=w_end,
                                state=result.state,
                                confidence=result.confidence,
                                source="model",
                            )
                        )

                self.progress.emit(min(b_start + len(chunk), total), total)

            # Collapse consecutive same-label windows into single segments
            # before persisting, instead of one row per window.
            merged_segments = merge_consecutive_segments(raw_segments)

            persistable_segments = [
                seg for seg in merged_segments if seg.state != "no-play"
            ]

            self.db.save_game_state_segments(
                media_path=self.video_path,
                media_type=self.media_type,
                width=self.width,
                height=self.height,
                start_frame=self.start_frame,
                end_frame=self.end_frame,
                segments=persistable_segments,
            )

            self.finished.emit(len(persistable_segments))

        except Exception as e:
            msg = str(e)
            if "out of memory" in msg.lower():
                msg = (f"GPU ran out of memory with batch size {self.batch_size}. "
                       f"Try a smaller batch size.\n\n{msg}")
            self.error.emit(msg)
        finally:
            cap.release()