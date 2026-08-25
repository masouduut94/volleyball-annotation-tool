from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox
from PyQt6.QtWidgets import QToolButton


def information_box(window: QMainWindow, message: str, ttl: int = 3000):
    message_label = QLabel(message, window)
    message_label.setStyleSheet(
        """
            background-color: #333;
            color: white;
            padding: 20px 20px;
            border-radius: 5px;
            font-size: 20px;
        """
    )
    message_label.adjustSize()
    message_label.move((window.width() - message_label.width()) // 2, 50)
    message_label.show()
    QTimer.singleShot(ttl, message_label.hide)


def create_help_button(text: str, parent=None) -> QToolButton:
    button = QToolButton(parent)
    button.setText("ⓘ")
    button.setAutoRaise(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)

    # Store help text
    button.help_text = text

    # Connect click event
    button.clicked.connect(lambda: show_help_dialog(text, button))

    button.setToolTip(f"Click for help - {text[:50]}...")

    button.setStyleSheet(
        """
            QToolButton {
                border: none;
                color: #8A93A3;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
                min-width: 20px;
                min-height: 20px;
            }

            QToolButton:hover {
                color: #E6E6E6;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }
        """
    )

    return button


def show_help_dialog(text: str, parent=None):
    # Option 1: Message box
    QMessageBox.information(
        parent,
        "Information",
        text
    )

    # Option 2: Tooltip (shows longer tooltip)
    # QToolTip.showText(parent.mapToGlobal(QPoint(0, 0)), text, parent)
