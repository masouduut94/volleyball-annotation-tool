from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QMainWindow


def information_box(window: QMainWindow, message: str, ttl: int = 3000):
    message_label = QLabel(message, window)
    message_label.setStyleSheet(
        "background-color: #333; color: white; padding: 20px 20px; "
        "border-radius: 5px; font-size: 20px;"
    )
    message_label.adjustSize()
    message_label.move((window.width() - message_label.width()) // 2, 50)
    message_label.show()
    QTimer.singleShot(ttl, message_label.hide)