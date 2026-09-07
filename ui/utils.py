from PyQt6.QtWidgets import QToolButton, QStyleOptionButton, QStyle, QWidget, QVBoxLayout
from PyQt6.QtGui import QIcon, QPainter, QPainterPath, QColor
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox, QPushButton
from PyQt6.QtCore import (QTimer, Qt, pyqtProperty, QSize, QPropertyAnimation, QEasingCurve, QRect, QPoint)


class CustomToolTip(QWidget):
    TRIANGLE_HEIGHT = 6

    def __init__(self, text="", parent=None):
        super().__init__(
            parent,
            Qt.WindowType.ToolTip |
            Qt.WindowType.FramelessWindowHint
        )

        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.text_label = QLabel(text, self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 400;
                background: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            10,  # left
            5,  # top
            10,  # right
            11  # bottom = space for triangle
        )

        layout.setSpacing(0)
        layout.addWidget(self.text_label)

        self.adjustSize()

    def setText(self, text):
        self.text_label.setText(text)
        self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect_height = (self.height() - self.TRIANGLE_HEIGHT)
        # Main rectangle
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), rect_height, 4, 4)

        # Bottom triangle
        center_x = self.width() / 2
        triangle = QPainterPath()
        triangle.moveTo(center_x - 6, rect_height)
        triangle.lineTo(center_x + 6, rect_height)
        triangle.lineTo(center_x, self.height())

        triangle.closeSubpath()
        path.addPath(triangle)
        painter.fillPath(path, QColor("#1E1E1E"))


class AnimatedIconButton(QPushButton):

    def __init__(
            self,
            icon_path: str,
            object_name: str,
            tooltip: str = "",
            icon_size: int = 25,
            parent=None,
    ):
        super().__init__(parent)

        self.setObjectName(object_name)

        # Store tooltip text
        self._tooltip_text = tooltip
        self._custom_tooltip = None

        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setIcon(QIcon(icon_path))

        # Base icon size
        self._base_icon_size = icon_size
        self._current_icon_size = icon_size

        self.setIconSize(QSize(icon_size, icon_size))

        # Button stays slightly larger than icon
        self.setFixedSize(icon_size + 12, icon_size + 12)

        # Animation
        self._animation = QPropertyAnimation(
            self,
            b"animatedIconSize",
            self
        )

        self._animation.setDuration(120)
        self._animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        # Tooltip delay
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(
            self._show_custom_tooltip
        )

    # --------------------------------------------------
    # Animated Property
    # --------------------------------------------------

    def getAnimatedIconSize(self):
        return self._current_icon_size

    def setAnimatedIconSize(self, value):
        self._current_icon_size = int(value)

        self.setIconSize(
            QSize(
                self._current_icon_size,
                self._current_icon_size
            )
        )

    animatedIconSize = pyqtProperty(
        int,
        fget=getAnimatedIconSize,
        fset=setAnimatedIconSize,
    )

    # --------------------------------------------------
    # Hover Events
    # --------------------------------------------------

    def enterEvent(self, event):

        # Animate icon
        self._animate_icon(self._base_icon_size, int(self._base_icon_size * 1.25))

        # Start tooltip timer
        if self._tooltip_text:
            self._tooltip_timer.start(500)

        super().enterEvent(event)

    def leaveEvent(self, event):

        # Animate icon back
        self._animate_icon(
            self._current_icon_size,
            self._base_icon_size
        )

        # Stop pending tooltip
        self._tooltip_timer.stop()

        # Hide tooltip
        self._hide_custom_tooltip()

        super().leaveEvent(event)

    # --------------------------------------------------
    # Tooltip
    # --------------------------------------------------

    def _show_custom_tooltip(self):

        if not self._tooltip_text:
            return

        if self._custom_tooltip is None:
            self._custom_tooltip = CustomToolTip(self._tooltip_text)

        else:
            self._custom_tooltip.setText(self._tooltip_text)

        self._custom_tooltip.adjustSize()
        # Get global position of button
        button_pos = self.mapToGlobal(QPoint(0, 0))
        tooltip_width = self._custom_tooltip.width()
        tooltip_height = self._custom_tooltip.height()

        # Center tooltip horizontally above button
        x = (button_pos.x() + self.width() // 2 - tooltip_width // 2)
        # Position above button
        y = (button_pos.y() - tooltip_height - 5)
        self._custom_tooltip.move(x, y)
        self._custom_tooltip.show()

    def _hide_custom_tooltip(self):
        if self._custom_tooltip is not None:
            self._custom_tooltip.hide()

    # --------------------------------------------------
    # Animation Helper
    # --------------------------------------------------

    def _animate_icon(self, start, end):
        self._animation.stop()
        self._animation.setStartValue(start)
        self._animation.setEndValue(end)
        self._animation.start()

    # --------------------------------------------------
    # Painting
    # --------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        # Draw button background
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        self.style().drawControl(
            QStyle.ControlElement.CE_PushButtonBevel,
            opt,
            painter,
            self
        )
        # Draw icon centered
        icon = self.icon()
        if not icon.isNull():
            icon_size = self.iconSize()
            rect = self.rect()

            x = (rect.width() - icon_size.width()) // 2
            y = (rect.height() - icon_size.height()) // 2

            icon.paint(
                painter,
                QRect(x, y, icon_size.width(), icon_size.height())
            )


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
    QMessageBox.information(parent, "Information", text)

    # Option 2: Tooltip (shows longer tooltip)
    # QToolTip.showText(parent.mapToGlobal(QPoint(0, 0)), text, parent)


def create_navigation_button(
        tooltip: str,
        icon_path: str,
        callback,
        object_name,
        icon_size=25,
):
    """Create an icon-only navigation button."""
    btn = AnimatedIconButton(
        icon_path=icon_path,
        tooltip=tooltip,
        icon_size=icon_size,
        object_name=object_name
    )
    btn.clicked.connect(callback)
    return btn
