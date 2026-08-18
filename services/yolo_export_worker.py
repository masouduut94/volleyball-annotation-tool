from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
)


class YOLOExportWorker(QObject):

    progress = pyqtSignal(int)

    finished = pyqtSignal()

    cancelled = pyqtSignal()

    error = pyqtSignal(str)

    def __init__(
            self,
            db,
            settings,
    ):

        super().__init__()

        self.db = db
        self.settings = settings

        self._cancel_requested = False

    # ==========================================================

    def cancel(self):

        self._cancel_requested = True

    # ==========================================================

    def is_cancelled(self):

        return self._cancel_requested

    # ==========================================================

    @pyqtSlot()
    def run(self):

        try:

            from .yolo_exporter import (
                YOLOExporter
            )

            exporter = YOLOExporter(
                self.db
            )

            completed = exporter.export(
                output_dir=self.settings[
                    "output_dir"
                ],
                mode=self.settings[
                    "mode"
                ],
                output_format=self.settings[
                    "format"
                ],
                selected_layers=self.settings[
                    "layers"
                ],
                selected_labels=self.settings[
                    "labels"
                ],
                selected_videos=self.settings[
                    "videos"
                ],
                augmentations=self.settings[
                    "augmentations"
                ],
                validation_ratio=self.settings[
                    "validation_ratio"
                ],
                progress_callback=self.progress.emit,
                cancel_callback=self.is_cancelled,
            )

            if self._cancel_requested:

                self.cancelled.emit()

            else:

                self.finished.emit()

        except Exception as e:

            self.error.emit(
                str(e)
            )