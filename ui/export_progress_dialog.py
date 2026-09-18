from PyQt6.QtCore import Qt, QTimer, QElapsedTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton


class ExportProgressDialog(QDialog):
    """
    Generic modal progress dialog, originally built for YOLO export.
    Title/labels are now configurable so other background jobs (e.g.
    game-state classification) can reuse this widget with their own
    wording instead of showing "Exporting YOLO Dataset".
    """

    def __init__(
            self,
            parent=None,
            window_title: str = "Exporting YOLO Dataset",
            preparing_text: str = "Preparing export...",
            progress_verb: str = "Exporting dataset",
            finished_text: str = "Export completed.",
            cancelled_text: str = "Export cancelled.",
            error_text: str = "Export failed.",
    ):
        super().__init__(parent)

        self.setWindowTitle(window_title)

        self.setFixedSize(420, 150)

        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # Stashed so set_progress/set_finished/etc. can build their text
        # without every call site having to pass strings each time.
        self._progress_verb = progress_verb
        self._finished_text = finished_text
        self._cancelled_text = cancelled_text
        self._error_text = error_text

        layout = QVBoxLayout(self)

        self.status_label = QLabel(preparing_text)

        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(0, 100)

        self.progress_bar.setValue(0)

        layout.addWidget(self.progress_bar)

        self.elapsed_label = QLabel("Elapsed: 00:00:00")

        layout.addWidget(self.elapsed_label)

        self.cancel_button = QPushButton("Cancel")

        layout.addWidget(self.cancel_button)

        self._cancelled = False

        # Elapsed-time tracking: a QElapsedTimer for accurate monotonic
        # timing, driven by a QTimer that ticks once a second to refresh
        # the label.
        self._elapsed_timer = QElapsedTimer()
        self._elapsed_timer.start()

        self._elapsed_refresh_timer = QTimer(self)
        self._elapsed_refresh_timer.setInterval(1000)
        self._elapsed_refresh_timer.timeout.connect(self._update_elapsed_label)
        self._elapsed_refresh_timer.start()

        # Show 00:00:00 immediately instead of waiting a full second.
        self._update_elapsed_label()

    # ==========================================================

    def _update_elapsed_label(self):
        total_seconds = self._elapsed_timer.elapsed() // 1000
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_label.setText(f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}")

    # ==========================================================

    def _stop_elapsed_timer(self):
        # Freeze the label at the final time rather than leaving it
        # ticking after the job is done/cancelled/errored.
        self._update_elapsed_label()
        self._elapsed_refresh_timer.stop()

    # ==========================================================

    def set_progress(self, value, detail: str = None):
        self.progress_bar.setValue(value)
        if detail:
            self.status_label.setText(f"{self._progress_verb}... {value}% ({detail})")
        else:
            self.status_label.setText(f"{self._progress_verb}... {value}%")

    # ==========================================================

    def set_finished(self):
        self.status_label.setText(self._finished_text)
        self.progress_bar.setValue(100)
        self.cancel_button.setEnabled(False)
        self._stop_elapsed_timer()

    # ==========================================================

    def set_cancelled(self):
        self.status_label.setText(self._cancelled_text)
        self.cancel_button.setEnabled(False)
        self._stop_elapsed_timer()

    # ==========================================================

    def set_error(self, message):
        self.status_label.setText(self._error_text)
        self.cancel_button.setEnabled(False)
        self.error_message = message
        self._stop_elapsed_timer()