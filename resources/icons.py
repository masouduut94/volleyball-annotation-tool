import math
from PyQt6.QtGui import QPixmap, QPainter, QPen, QPolygonF, QIcon
from PyQt6.QtCore import pyqtProperty, QPointF, QRectF, Qt, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QPushButton


def rectangle_icon(size=28):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(Qt.GlobalColor.white, max(2, size // 12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    # centered rectangle
    margin = size * 0.18
    rect = QRectF(margin, size * 0.22,
                  size - 2 * margin,
                  size * 0.56)
    p.drawRoundedRect(rect, size * 0.08, size * 0.08)

    p.end()
    return QIcon(pix)


def polygon_icon(size=28, sides=6):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = size * 0.18
    radius = (size / 2) - margin
    center = QPointF(size / 2, size / 2)

    pen = QPen(Qt.GlobalColor.white, max(2, size // 12))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    points = []
    start_angle = -math.pi / 2  # start from top

    for i in range(sides):
        angle = start_angle + (2 * math.pi * i / sides)
        x = center.x() + radius * math.cos(angle)
        y = center.y() + radius * math.sin(angle)
        points.append(QPointF(x, y))

    poly = QPolygonF(points)
    p.drawPolygon(poly)

    # vertex dots
    dot_radius = max(1.5, size * 0.06)
    p.setBrush(Qt.GlobalColor.white)
    p.setPen(Qt.PenStyle.NoPen)

    for pt in points:
        p.drawEllipse(pt, dot_radius, dot_radius)

    p.end()
    return QIcon(pix)


class AnimatedIconButton(QPushButton):

    def __init__(
            self,
            icon_path: str,
            tooltip: str = "",
            icon_size: int = 25,
            object_name: str = "navigationButton",
            parent=None,
    ):
        super().__init__(parent)

        self.setObjectName(object_name)
        self.setToolTip(tooltip)
        self.setIcon(QIcon(icon_path))

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
        self.setIconSize(QSize(self._current_icon_size, self._current_icon_size))

    animatedIconSize = pyqtProperty(
        int,
        fget=getAnimatedIconSize,
        fset=setAnimatedIconSize,
    )

    # --------------------------------------------------
    # Hover Events
    # --------------------------------------------------

    def enterEvent(self, event):
        self._animate_icon(self._base_icon_size, int(self._base_icon_size * 1.25))
        super().enterEvent(event)

    def leaveEvent(self, event):
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
