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
            # Extend the running segment.
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
    progress = pyqtSignal(int, int)   # windows_done, windows_total
    finished = pyqtSignal(int)        # segments saved (post-merge)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, db, classifier, video_path, media_type, width, height,
                 start_frame, end_frame, window_size=30, parent=None):
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
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        # Own VideoCapture instance — don't share MainWindow's across threads.
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.error.emit(f"Could not open video: {self.video_path}")
            return

        windows = list(range(self.start_frame, self.end_frame + 1, self.window_size))
        total = len(windows)
        raw_segments = []

        try:
            for i, w_start in enumerate(windows):
                if self._cancelled:
                    self.cancelled.emit()
                    return

                w_end = min(w_start + self.window_size - 1, self.end_frame)

                frames = []
                cap.set(cv2.CAP_PROP_POS_FRAMES, w_start)
                for _ in range(w_end - w_start + 1):
                    ok, frame = cap.read()
                    if not ok:
                        break
                    frames.append(frame)

                if frames:
                    result = self.classifier.classify(frames)
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

                self.progress.emit(i + 1, total)

            # NEW — collapse consecutive same-label windows into single
            # segments before persisting, instead of one row per window.
            merged_segments = merge_consecutive_segments(raw_segments)

            self.db.save_game_state_segments(
                media_path=self.video_path,
                media_type=self.media_type,
                width=self.width,
                height=self.height,
                start_frame=self.start_frame,
                end_frame=self.end_frame,
                segments=merged_segments,
            )

            self.finished.emit(len(merged_segments))

        except Exception as e:
            self.error.emit(str(e))
        finally:
            cap.release()