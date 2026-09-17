"""
An animated slide switch (macOS/iOS style), used for the Dark/Light
control in the top toolbar. Built as a checkable QAbstractButton rather
than a pure-QSS trick, since a smoothly-sliding thumb needs real
animation — QAbstractButton gives click/keyboard toggling for free while
leaving all the drawing to us.
"""

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QAbstractButton, QSizePolicy

from .colors import Colors


class ThemeToggleSwitch(QAbstractButton):
    """checked=True means LIGHT theme; unchecked means DARK theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip("Toggle Dark / Light theme")

        self._track_w, self._track_h = 44, 24
        self._thumb_margin = 2
        self._thumb_d = self._track_h - self._thumb_margin * 2
        self._thumb_pos = self._thumb_margin  # animated property

        self._anim = QPropertyAnimation(self, b"thumbPos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.toggled.connect(self._animate_to_state)

    def getThumbPos(self):
        return self._thumb_pos

    def setThumbPos(self, value):
        self._thumb_pos = value
        self.update()

    thumbPos = pyqtProperty(float, fget=getThumbPos, fset=setThumbPos)

    def _animate_to_state(self, checked):
        end = (self._track_w - self._thumb_margin - self._thumb_d) if checked else self._thumb_margin
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(end)
        self._anim.start()

    def setChecked(self, checked):
        """Jump instantly, no animation — used only to sync state (e.g.
        restoring a saved theme at startup), not on user interaction."""
        super().setChecked(checked)
        self._thumb_pos = (
            (self._track_w - self._thumb_margin - self._thumb_d) if checked else self._thumb_margin
        )
        self.update()

    def sizeHint(self):
        return QSize(self._track_w, self._track_h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_rect = QRectF(0, 0, self._track_w, self._track_h)
        track_color = QColor(Colors.ACCENT) if self.isChecked() else QColor(Colors.BORDER_HOVER)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, self._track_h / 2, self._track_h / 2)

        thumb_rect = QRectF(self._thumb_pos, self._thumb_margin, self._thumb_d, self._thumb_d)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(thumb_rect)