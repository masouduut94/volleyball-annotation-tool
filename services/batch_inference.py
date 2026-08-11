from PyQt6.QtCore import QThread, pyqtSignal
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


class BatchInferenceWorker(QThread):
    progress_changed = pyqtSignal(int, int)
    status_changed = pyqtSignal(str)
    finished_successfully = pyqtSignal(dict)

    def __init__(
        self,
        main_window,
        selected_models,
        start_frame,
        end_frame,
    ):
        super().__init__()

        self.main_window = main_window
        self.selected_models = selected_models
        self.start_frame = start_frame
        self.end_frame = end_frame

        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    def run(self):
        stats = {
            "frames": 0,
            "imported": 0,
        }

        total = self.end_frame - self.start_frame + 1

        for i, frame_number in enumerate(
            range(self.start_frame, self.end_frame + 1)
        ):
            if self.cancel_requested:
                return

            self.progress_changed.emit(i + 1, total)

            self.status_changed.emit(
                f"Processing frame {frame_number}"
            )

            count = self.main_window.run_batch_inference_on_frame(
                frame_number=frame_number,
                model_keys=self.selected_models,
            )

            stats["frames"] += 1
            stats["imported"] += count

        self.finished_successfully.emit(stats)


class BatchInferenceDialog(QDialog):
    def __init__(self, db, auto_annotator, main_window, parent=None):
        super().__init__(parent)

        self.db = db
        self.auto_annotator = auto_annotator
        self.main_window = main_window

        self.worker = None

        self.setWindowTitle("AI batch inference")
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

        title = QLabel("Use models")
        title.setStyleSheet(
            "font-weight:bold; font-size:14px;"
        )
        layout.addWidget(title)

        self.ball_cb = QCheckBox("Ball segmentation")
        self.court_cb = QCheckBox("Court segmentation")
        self.actions_cb = QCheckBox("Actions detection")
        self.players_cb = QCheckBox("Players detection")

        layout.addWidget(self.ball_cb)
        layout.addWidget(self.court_cb)
        layout.addWidget(self.actions_cb)
        layout.addWidget(self.players_cb)

        # --------------------------------------------------
        # Target job
        # --------------------------------------------------
        layout.addSpacing(10)

        layer_title = QLabel("Target layers")
        layer_title.setStyleSheet(
            "font-weight:bold; font-size:14px;"
        )
        layout.addWidget(layer_title)

        layout.addWidget(
            QLabel("Court model → Court layer")
        )

        layout.addWidget(
            QLabel("Players model → Players layer")
        )

        layout.addWidget(
            QLabel("Ball model → Ball layer")
        )

        layout.addWidget(
            QLabel("Actions model → Actions layer")
        )

        # --------------------------------------------------
        # Frames
        # --------------------------------------------------

        layout.addSpacing(10)

        frames_title = QLabel("Frames")
        frames_title.setStyleSheet(
            "font-weight:bold; font-size:14px;"
        )
        layout.addWidget(frames_title)

        self.all_frames_cb = QCheckBox(
            "Annotate all frames"
        )
        self.all_frames_cb.setChecked(True)
        self.all_frames_cb.toggled.connect(
            self.on_all_frames_changed
        )
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
        progress_title.setStyleSheet(
            "font-weight:bold; font-size:14px;"
        )
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

        if self.court_cb.isChecked():
            models.append("court")

        if self.actions_cb.isChecked():
            models.append("actions")

        if self.players_cb.isChecked():
            models.append("players")

        return models

    def start_inference(self):
        models = self.selected_models()

        if not models:
            QMessageBox.warning(
                self,
                "No model selected",
                "Please select at least one model.",
            )
            return

        if self.all_frames_cb.isChecked():
            start = 0
            end = self.main_window.total_frames - 1
        else:
            start = self.start_spin.value()
            end = self.end_spin.value()

        if start > end:
            QMessageBox.warning(
                self,
                "Invalid frame range",
                "The start frame must be less than or equal to the end frame.",
            )
            return

        self.run_btn.setEnabled(False)

        self.worker = BatchInferenceWorker(
            self.main_window,
            models,
            start,
            end,
        )

        self.worker.progress_changed.connect(
            self.update_progress
        )

        self.worker.status_changed.connect(
            self.progress_label.setText
        )

        self.worker.finished_successfully.connect(
            self.on_finished
        )

        self.worker.start()

    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

        self.progress_label.setText(
            f"Processing {current}/{total}"
        )

    def on_finished(self, stats):
        self.run_btn.setEnabled(True)

        QMessageBox.information(
            self,
            "Batch inference complete",
            (
                f"Frames processed: {stats['frames']}\\n"
                f"Annotations imported: {stats['imported']}"
            ),
        )

        self.main_window.load_annotations()

    def on_cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        else:
            self.reject()
