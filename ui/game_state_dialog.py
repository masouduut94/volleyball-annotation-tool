from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QSpinBox,
    QDoubleSpinBox,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QHBoxLayout,
)


class GameStateRangeDialog(QDialog):
    """
    Configuration for a game-state classification job.

    Includes the minimum allowed gap used by the post-inference
    game-state gap filling.
    """

    def __init__(
            self,
            max_frame,
            current_frame=0,
            default_window=30,
            default_min_gap_seconds=2.0,
            parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Classify Game State")
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Classifies the selected range into service / play / no-play "
            "windows (~1s each) and paints the result on the seek bar."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()

        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, max_frame)
        self.start_spin.setValue(0)

        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, max_frame)
        self.end_spin.setValue(max_frame)

        self.window_spin = QSpinBox()
        self.window_spin.setRange(5, 300)
        self.window_spin.setValue(default_window)
        self.window_spin.setSuffix(" frames")

        # Minimum gap duration used after inference.
        self.min_gap_spin = QDoubleSpinBox()
        self.min_gap_spin.setRange(0.1, 30.0)
        self.min_gap_spin.setSingleStep(0.5)
        self.min_gap_spin.setDecimals(1)
        self.min_gap_spin.setValue(default_min_gap_seconds)
        self.min_gap_spin.setSuffix(" seconds")

        form.addRow("Start frame", self.start_spin)
        form.addRow("End frame", self.end_spin)
        form.addRow("Window size", self.window_spin)
        form.addRow("Min gap", self.min_gap_spin)

        layout.addLayout(form)

        quick_row = QHBoxLayout()

        use_current_start = QPushButton("Use current as start")
        use_current_end = QPushButton("Use current as end")

        use_current_start.clicked.connect(
            lambda: self.start_spin.setValue(current_frame)
        )
        use_current_end.clicked.connect(
            lambda: self.end_spin.setValue(current_frame)
        )

        quick_row.addWidget(use_current_start)
        quick_row.addWidget(use_current_end)

        layout.addLayout(quick_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def get_settings(self):
        start = self.start_spin.value()
        end = self.end_spin.value()

        if start > end:
            start, end = end, start

        return {
            "start_frame": start,
            "end_frame": end,
            "window_size": self.window_spin.value(),
            "min_gap_seconds": self.min_gap_spin.value(),
        }