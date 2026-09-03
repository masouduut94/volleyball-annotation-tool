from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QSpinBox,
                              QDialogButtonBox, QLabel, QPushButton, QHBoxLayout)


class GameStateRangeDialog(QDialog):
    """
    Configuration for a game-state classification job. Unlike the
    per-frame detectors, this always needs a range — so it's a dialog,
    not a one-click button.
    """

    def __init__(
            self,
            max_frame,
            current_frame=0,
            default_window=30,
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

        form.addRow("Start frame", self.start_spin)
        form.addRow("End frame", self.end_spin)
        form.addRow("Window size", self.window_spin)
        layout.addLayout(form)

        quick_row = QHBoxLayout()
        use_current_start = QPushButton("Use current as start")
        use_current_end = QPushButton("Use current as end")
        use_current_start.clicked.connect(lambda: self.start_spin.setValue(current_frame))
        use_current_end.clicked.connect(lambda: self.end_spin.setValue(current_frame))
        quick_row.addWidget(use_current_start)
        quick_row.addWidget(use_current_end)
        layout.addLayout(quick_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
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
        }