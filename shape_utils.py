from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QFont
from PyQt6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsPolygonItem,
    QGraphicsTextItem,
)


class BaseAnnotationItem:

    def __init__(self):
        self.layer_name = None

    def _setup_style(self, color: str, label: str = ""):
        self.annotation_color = QColor(color)
        self.label = label

        self.layer_name = "court"

        self.fill_alpha = 40
        self.hover_fill_alpha = 80

        self.normal_pen = QPen(self.annotation_color, 2)
        self.hover_pen = QPen(self.annotation_color.lighter(150), 3)
        self.selected_pen = QPen(QColor("#FFFF00"), 3)

        self.normal_brush = QBrush(
            QColor(
                self.annotation_color.red(),
                self.annotation_color.green(),
                self.annotation_color.blue(),
                self.fill_alpha,
            )
        )

        self.hover_brush = QBrush(
            QColor(
                self.annotation_color.red(),
                self.annotation_color.green(),
                self.annotation_color.blue(),
                self.hover_fill_alpha,
            )
        )

        # Setup label
        self._setup_label()

    def _setup_label(self):
        """Create and setup the label text item"""
        if hasattr(self, 'label_item'):
            # Remove existing label if it exists
            if self.label_item.scene():
                self.label_item.scene().removeItem(self.label_item)

        if self.label:
            self.label_item = QGraphicsTextItem(self.label, self)
            self.label_item.setDefaultTextColor(Qt.GlobalColor.white)
            self.label_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))

            # Add background to label for better visibility
            self.label_item.setHtml(
                f'<div style="background-color: rgba(0,0,0,150); '
                f'padding: 2px 6px; border-radius: 3px;">'
                f'{self.label}</div>'
            )

            # Position label at top-center of the item
            self._update_label_position()
            self.label_item.setZValue(self.zValue() + 1)
        else:
            self.label_item = None

    def _update_label_position(self):
        """Update the position of the label based on item bounds"""
        if self.label_item:
            bounds = self.boundingRect()
            label_width = self.label_item.boundingRect().width()

            # Position at top-center
            x = bounds.x() + (bounds.width() - label_width) / 2
            y = bounds.y() - self.label_item.boundingRect().height() - 2

            self.label_item.setPos(QPointF(x, y))

    def _apply_normal(self):
        self.setPen(self.normal_pen)
        self.setBrush(self.normal_brush)
        if self.label_item:
            self.label_item.setDefaultTextColor(Qt.GlobalColor.white)

    def _apply_hover(self):
        self.setPen(self.hover_pen)
        self.setBrush(self.hover_brush)
        if self.label_item:
            self.label_item.setDefaultTextColor(Qt.GlobalColor.yellow)

    def _apply_selected(self):
        self.setPen(self.selected_pen)
        self.setBrush(self.hover_brush)
        if self.label_item:
            self.label_item.setDefaultTextColor(Qt.GlobalColor.yellow)

    def set_label(self, label: str):
        """Update the label text"""
        self.label = label
        self._setup_label()

    def set_annotation_color(self, color: str):
        self._setup_style(color, self.label)
        if self.isSelected():
            self._apply_selected()
        else:
            self._apply_normal()

    def set_layer(self, layer_name: str):
        self.layer_name = layer_name


class AnnotationRectItem(QGraphicsRectItem, BaseAnnotationItem):
    def __init__(self, rect, color: str, label: str = ""):
        QGraphicsRectItem.__init__(self, rect)

        self._setup_style(color, label)
        self._apply_normal()

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)

    def _update_label_position(self):
        """Update label position for rectangle"""
        if self.label_item:
            rect = self.rect()
            label_width = self.label_item.boundingRect().width()

            x = rect.x() + (rect.width() - label_width) / 2
            y = rect.y() - self.label_item.boundingRect().height() - 2

            self.label_item.setPos(QPointF(x, y))

    def hoverEnterEvent(self, event):
        if self.scene():
            self.scene().set_hovered_item(self)

        if not self.isSelected():
            self._apply_hover()

        QGraphicsRectItem.hoverEnterEvent(self, event)

    def hoverLeaveEvent(self, event):
        if self.scene():
            self.scene().clear_hovered_item(self)

        if self.isSelected():
            self._apply_selected()
        else:
            self._apply_normal()

        QGraphicsRectItem.hoverLeaveEvent(self, event)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemSelectedHasChanged:
            if bool(value):
                self._apply_selected()
            else:
                self._apply_normal()
        elif change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            self._update_label_position()
        elif change == QGraphicsRectItem.GraphicsItemChange.ItemTransformHasChanged:
            self._update_label_position()

        return QGraphicsRectItem.itemChange(self, change, value)


class AnnotationPolygonItem(QGraphicsPolygonItem, BaseAnnotationItem):
    def __init__(self, polygon, color: str, label: str = ""):
        QGraphicsPolygonItem.__init__(self, polygon)

        self._setup_style(color, label)
        self._apply_normal()

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsMovable, True)

    def _update_label_position(self):
        """Update label position for polygon (centered on bounding rect)"""
        if self.label_item:
            bounds = self.boundingRect()
            label_width = self.label_item.boundingRect().width()

            x = bounds.x() + (bounds.width() - label_width) / 2
            y = bounds.y() - self.label_item.boundingRect().height() - 2

            self.label_item.setPos(QPointF(x, y))

    def hoverEnterEvent(self, event):
        if self.scene():
            self.scene().set_hovered_item(self)

        if not self.isSelected():
            self._apply_hover()

        QGraphicsPolygonItem.hoverEnterEvent(self, event)

    def hoverLeaveEvent(self, event):
        if self.scene():
            self.scene().clear_hovered_item(self)

        if self.isSelected():
            self._apply_selected()
        else:
            self._apply_normal()

        QGraphicsPolygonItem.hoverLeaveEvent(self, event)

    def itemChange(self, change, value):
        if change == QGraphicsPolygonItem.GraphicsItemChange.ItemSelectedHasChanged:
            if bool(value):
                self._apply_selected()
            else:
                self._apply_normal()
        elif change == QGraphicsPolygonItem.GraphicsItemChange.ItemPositionHasChanged:
            self._update_label_position()
        elif change == QGraphicsPolygonItem.GraphicsItemChange.ItemTransformHasChanged:
            self._update_label_position()

        return QGraphicsPolygonItem.itemChange(self, change, value)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(self.pen())
        painter.setBrush(self.brush())

        painter.drawPolygon(self.polygon())

        # Draw vertices
        painter.setBrush(QBrush(self.annotation_color))
        painter.setPen(QPen(Qt.GlobalColor.white, 1))

        radius = 1

        for point in self.polygon():
            painter.drawEllipse(point, radius, radius)
