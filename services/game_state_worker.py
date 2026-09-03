import cv2
from PyQt6.QtCore import QObject, pyqtSignal

from src.vb_gui.vb_annotator.database.data import GameStateSegment


class GameStateWorker(QObject):
    progress = pyqtSignal(int, int)   # windows_done, windows_total
    finished = pyqtSignal(int)        # segments saved
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
        segments = []

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
                    segments.append(
                        GameStateSegment(
                            media_name=self.video_path,
                            start_frame=w_start,
                            end_frame=w_end,
                            state=result.state,
                            confidence=result.confidence,
                            source="model",  # NEW — distinguishes from manual tags for training-set curation
                        )
                    )

                self.progress.emit(i + 1, total)

            self.db.save_game_state_segments(
                media_path=self.video_path,
                media_type=self.media_type,
                width=self.width,
                height=self.height,
                start_frame=self.start_frame,
                end_frame=self.end_frame,
                segments=segments,
            )

            self.finished.emit(len(segments))

        except Exception as e:
            self.error.emit(str(e))
        finally:
            cap.release()