from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QGraphicsView


class GraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.space_pressed = False
        self.panning = False

        self.zoom_factor = 1.15
        self.min_scale = 0.1
        self.max_scale = 20.0
        self.current_scale = 1.0

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )

        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.setBackgroundBrush(Qt.GlobalColor.black)

        self._panning = False
        self._pan_start = None

    # ---------------------------------------------------------
    # Fit image
    # ---------------------------------------------------------

    def fit_image(self):
        if self.scene() is None:
            return

        rect = self.scene().itemsBoundingRect()

        if rect.isEmpty():
            return

        self.resetTransform()

        self.fitInView(
            rect,
            Qt.AspectRatioMode.KeepAspectRatio,
        )

        self.current_scale = self.transform().m11()

    def reset_view(self):
        self.fit_image()

    # ---------------------------------------------------------
    # Zoom
    # ---------------------------------------------------------

    def zoom_in(self):
        self.apply_zoom(self.zoom_factor)

    def zoom_out(self):
        self.apply_zoom(1.0 / self.zoom_factor)

    def apply_zoom(self, factor):
        new_scale = self.current_scale * factor

        if new_scale < self.min_scale:
            return

        if new_scale > self.max_scale:
            return

        self.scale(factor, factor)
        self.current_scale = new_scale

    # ---------------------------------------------------------
    # Mouse wheel
    # ---------------------------------------------------------

    def wheelEvent(self, event):
        delta = event.angleDelta().y()

        if delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

        event.accept()

    # ---------------------------------------------------------
    # Keyboard
    # ---------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_PageUp:
            self.zoom_in()
            event.accept()
            return

        if event.key() == Qt.Key.Key_PageDown:
            self.zoom_out()
            event.accept()
            return

        if event.key() == Qt.Key.Key_Home:
            self.reset_view()
            event.accept()
            return

        if event.key() == Qt.Key.Key_Space:
            self.space_pressed = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space_pressed = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        super().keyReleaseEvent(event)

    # ---------------------------------------------------------
    # Panning
    # ---------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()

            self.setCursor(Qt.CursorShape.ClosedHandCursor)

            event.accept()
            return

        if self.space_pressed and event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start

            self._pan_start = event.pos()

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )

            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

            event.accept()
            return

        if self.space_pressed:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

        super().mouseReleaseEvent(event)

    # ---------------------------------------------------------
    # Resize
    # ---------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if self.current_scale == 1.0:
            self.fit_image()