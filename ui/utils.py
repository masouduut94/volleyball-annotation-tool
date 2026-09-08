from PyQt6.QtWidgets import QToolButton, QStyleOptionButton, QStyle, QWidget, QVBoxLayout
from PyQt6.QtGui import QIcon, QPainter, QPainterPath, QColor
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox, QPushButton
from PyQt6.QtCore import (QTimer, Qt, pyqtProperty, QSize, QPropertyAnimation,
                          QEasingCurve, QRect, QPoint, QObject, QEvent)


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
                color: white;
                font-size: 11px;
                background: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 11)
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
        path = QPainterPath()

        # Main rounded rectangle
        path.addRoundedRect(0, 0, self.width(), rect_height, 4, 4)

        # Triangle
        center_x = self.width() / 2
        triangle = QPainterPath()
        triangle.moveTo(center_x - 6, rect_height)
        triangle.lineTo(center_x + 6, rect_height)
        triangle.lineTo(center_x, self.height())

        triangle.closeSubpath()
        path.addPath(triangle)
        painter.fillPath(path, QColor("#1E1E1E"))


class TooltipManager(QObject):
    def __init__(self, widget, text, position="top", delay=500):
        super().__init__(widget)

        self.widget = widget
        self.text = text
        self.position = position
        self.delay = delay

        self.tooltip = CustomToolTip(text)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.show_tooltip)
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.widget:
            if event.type() == QEvent.Type.Enter:
                self.timer.start(self.delay)

            elif event.type() == QEvent.Type.Leave:
                self.timer.stop()
                self.tooltip.hide()

        return super().eventFilter(obj, event)

    def show_tooltip(self):
        if not self.widget.isVisible():
            return

        self.tooltip.adjustSize()
        global_pos = self.widget.mapToGlobal(QPoint(0, 0))
        tooltip_width = self.tooltip.width()
        tooltip_height = self.tooltip.height()

        if self.position == "top":
            x = (global_pos.x() + self.widget.width() // 2 - tooltip_width // 2)
            y = (global_pos.y() - tooltip_height - 5)

        elif self.position == "bottom":
            x = (global_pos.x() + self.widget.width() // 2 - tooltip_width // 2)
            y = (global_pos.y() + self.widget.height() + 5)

        else:
            x = global_pos.x()
            y = global_pos.y()

        self.tooltip.move(x, y)
        self.tooltip.show()


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
        self._custom_tooltip_manager = None
        self.setObjectName(object_name)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(QIcon(icon_path))

        if tooltip:
            set_custom_tooltip(self, tooltip, position="top")

        # Base icon size
        self._base_icon_size = icon_size
        self._current_icon_size = icon_size
        self.setIconSize(QSize(icon_size, icon_size))

        # Button stays slightly larger than icon
        self.setFixedSize(icon_size + 12, icon_size + 12)
        # Animation
        self._animation = QPropertyAnimation(self, b"animatedIconSize", self)
        self._animation.setDuration(120)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

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
        super().enterEvent(event)

    def leaveEvent(self, event):

        # Animate icon back
        self._animate_icon(self._current_icon_size, self._base_icon_size)
        super().leaveEvent(event)

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


def set_custom_tooltip(widget, text, position="top", delay=500):
    tooltip_manager = TooltipManager(
        widget=widget,
        text=text,
        position=position,
        delay=delay,
    )

    # Store reference directly on widget
    widget._custom_tooltip_manager = tooltip_manager

    return tooltip_manager


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
        icon_size=icon_size,
        object_name=object_name,
        tooltip=tooltip
    )
    btn.clicked.connect(callback)
    return btn
