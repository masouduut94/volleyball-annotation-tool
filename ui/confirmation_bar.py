from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy


class ConfirmationBar(QWidget):
    """
    Thin strip above the graphics view showing whether the annotations for
    the CURRENT (frame, layer) pair have been confirmed by a human, plus a
    button (and the Ctrl+K shortcut, wired in MainWindow) to confirm them.
    """

    confirmRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("confirmationBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        self.status_icon = QLabel("!")
        self.status_icon.setObjectName("statusWarn")
        self.status_icon.setFixedWidth(16)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Not confirmed")
        self.status_label.setObjectName("confirmationText")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.confirm_button = QPushButton("Confirm Frame  (Ctrl+K)")
        self.confirm_button.setObjectName("confirmButton")
        self.confirm_button.setFixedHeight(28)
        self.confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_button.clicked.connect(self.confirmRequested.emit)

        layout.addWidget(self.status_icon)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.confirm_button)

    def set_confirmed(self, confirmed: bool, layer_name: str = "", frame_label: str = ""):
        self.setProperty("state", "confirmed" if confirmed else "unconfirmed")
        self.style().unpolish(self)
        self.style().polish(self)

        if confirmed:
            self.status_icon.setText("✓")
            self.status_icon.setObjectName("statusOk")
            text = "Confirmed"
        else:
            self.status_icon.setText("!")
            self.status_icon.setObjectName("statusWarn")
            text = "Not confirmed"
        self.status_icon.style().unpolish(self.status_icon)
        self.status_icon.style().polish(self.status_icon)

        if layer_name or frame_label:
            text = f"{text} — " + " · ".join(p for p in (layer_name, frame_label) if p)
        self.status_label.setText(text)
        self.confirm_button.setEnabled(not confirmed)
