from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QPushButton,
    QProgressBar,
    QListWidget,
    QMessageBox,
)

from vb_gui.vb_annotator.ui.theme import Typography
from vb_gui.vb_annotator.services.job_runner import run_background_job  # adjust path to match your project root if different


class BatchInferenceWorker(QObject):
    """
    Runs one or more AI models across a frame range, one frame at a time.

    Converted from a QThread subclass to a plain QObject so it can be run
    through run_background_job like every other worker in services/ —
    that also fixes two bugs the old QThread version had: a cancel
    request never told the dialog it had actually stopped (no signal was
    emitted, so the Run button stayed disabled forever), and an exception
    mid-loop would kill the thread silently with no error surfaced to
    the user at all.
    """

    progress = pyqtSignal(int, int)   # frames_done, frames_total
    status = pyqtSignal(str)          # human-readable "Processing frame N"
    finished = pyqtSignal(dict)       # {"frames": int, "imported": int}
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, main_window, selected_models, start_frame, end_frame, parent=None):
        super().__init__(parent)

        self.main_window = main_window
        self.selected_models = selected_models
        self.start_frame = start_frame
        self.end_frame = end_frame

        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        stats = {"frames": 0, "imported": 0}
        total = self.end_frame - self.start_frame + 1

        try:
            for i, frame_number in enumerate(range(self.start_frame, self.end_frame + 1)):
                if self._cancel_requested:
                    self.cancelled.emit()
                    return

                self.progress.emit(i + 1, total)
                self.status.emit(f"Processing frame {frame_number}")

                count = self.main_window.run_batch_inference_on_frame(
                    frame_number=frame_number,
                    model_keys=self.selected_models,
                )

                stats["frames"] += 1
                stats["imported"] += count

            self.finished.emit(stats)

        except Exception as e:
            self.error.emit(str(e))


class BatchInferenceDialog(QDialog):
    def __init__(self, db, auto_annotator, main_window, parent=None):
        super().__init__(parent)

        self.db = db
        self.auto_annotator = auto_annotator
        self.main_window = main_window

        self._job = None  # BackgroundJob — keeps worker+thread alive while running

        self.setWindowTitle("Quick-Annotate Menu")
        self.resize(560, 520)

        self.build_ui()

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def build_ui(self):
        layout = QVBoxLayout(self)

        # --------------------------------------------------
        # Use models
        # --------------------------------------------------

        title = QLabel("Models")
        layout.addWidget(title)

        self.ball_cb = QCheckBox("Ball segmentation")
        self.actions_cb = QCheckBox("Actions detection")
        self.players_cb = QCheckBox("Players detection")

        layout.addWidget(self.ball_cb)
        layout.addWidget(self.actions_cb)
        layout.addWidget(self.players_cb)

        # --------------------------------------------------
        # Target job
        # --------------------------------------------------
        layout.addSpacing(10)

        layer_title = QLabel("Target layers")
        layout.addWidget(layer_title)

        layout.addWidget(QLabel("Players model → Players layer"))
        layout.addWidget(QLabel("Ball model → Ball layer"))
        layout.addWidget(QLabel("Actions model → Actions layer"))

        # --------------------------------------------------
        # Frames
        # --------------------------------------------------

        layout.addSpacing(10)

        frames_title = QLabel("Frames")
        layout.addWidget(frames_title)

        self.all_frames_cb = QCheckBox("Annotate all frames")
        self.all_frames_cb.setChecked(True)
        self.all_frames_cb.toggled.connect(self.on_all_frames_changed)
        layout.addWidget(self.all_frames_cb)

        frame_row = QHBoxLayout()

        frame_row.addWidget(QLabel("From"))
        self.start_spin = QSpinBox()
        self.start_spin.setMaximum(10_000_000)
        frame_row.addWidget(self.start_spin)

        frame_row.addWidget(QLabel("To"))
        self.end_spin = QSpinBox()
        self.end_spin.setMaximum(10_000_000)
        frame_row.addWidget(self.end_spin)

        layout.addLayout(frame_row)

        # --------------------------------------------------
        # Progress
        # --------------------------------------------------

        layout.addSpacing(10)

        progress_title = QLabel("Progress")
        layout.addWidget(progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Ready")
        layout.addWidget(self.progress_label)

        # --------------------------------------------------
        # Buttons
        # --------------------------------------------------

        layout.addStretch()

        button_row = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.on_cancel)

        self.run_btn = QPushButton("Run inference")
        self.run_btn.clicked.connect(self.start_inference)

        button_row.addStretch()
        button_row.addWidget(self.cancel_btn)
        button_row.addWidget(self.run_btn)

        layout.addLayout(button_row)

        self.initialize_frame_range()

    # ---------------------------------------------------------
    # Frames
    # ---------------------------------------------------------

    def initialize_frame_range(self):
        if self.main_window.cap is not None:
            total = self.main_window.total_frames
            self.start_spin.setValue(0)
            self.end_spin.setValue(max(0, total - 1))

    def on_all_frames_changed(self, checked):
        self.start_spin.setEnabled(not checked)
        self.end_spin.setEnabled(not checked)

    # ---------------------------------------------------------
    # Inference
    # ---------------------------------------------------------

    def selected_models(self):
        models = []
        if self.ball_cb.isChecked():
            models.append("ball")
        if self.actions_cb.isChecked():
            models.append("actions")
        if self.players_cb.isChecked():
            models.append("players")
        return models

    def start_inference(self):
        models = self.selected_models()

        if not models:
            QMessageBox.warning(self, "No model selected", "Please select at least one model.")
            return

        if self.all_frames_cb.isChecked():
            start = 0
            end = self.main_window.total_frames - 1
        else:
            start = self.start_spin.value()
            end = self.end_spin.value()

        if start > end:
            QMessageBox.warning(
                self, "Invalid frame range",
                "The start frame must be less than or equal to the end frame.",
            )
            return

        self.run_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting…")

        worker = BatchInferenceWorker(self.main_window, models, start, end)

        # BatchInferenceWorker.progress carries (done, total) and this
        # dialog has its own inline progress bar/label rather than a
        # separate ExportProgressDialog, so wire those two directly
        # instead of going through run_background_job's generic
        # set_progress(int) auto-connect.
        worker.progress.connect(self.update_progress)
        worker.status.connect(self.progress_label.setText)

        self._job = run_background_job(
            parent=self,
            worker=worker,
            progress_dialog=self,   # only used for .show(); we handle progress/cancel ourselves
            on_finished=self.on_finished,
            on_cancelled=self.on_cancelled,
            on_error=self.on_error,
            connect_progress=False,
        )

    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processing {current}/{total}")

    def on_finished(self, stats):
        self.run_btn.setEnabled(True)
        self._job = None

        QMessageBox.information(
            self,
            "Batch inference complete",
            (
                f"Frames processed: {stats['frames']}\n"
                f"Annotations imported: {stats['imported']}"
            ),
        )

        self.main_window.load_annotations()

    def on_cancelled(self):
        """NEW — the old version never told the dialog a cancel actually
        completed, so the Run button stayed disabled and the progress
        label stayed frozen mid-run until the dialog was closed."""
        self.run_btn.setEnabled(True)
        self._job = None
        self.progress_label.setText("Cancelled.")

    def on_error(self, message):
        """NEW — the old version had no error signal at all, so an
        exception partway through the frame loop killed the thread
        silently with no feedback to the user."""
        self.run_btn.setEnabled(True)
        self._job = None
        self.progress_label.setText("Failed.")
        QMessageBox.critical(self, "Batch Inference Failed", f"Could not complete batch inference:\n\n{message}")

    def on_cancel(self):
        if self._job is not None and self._job.thread.isRunning():
            self._job.worker.cancel()
        else:
            self.reject()