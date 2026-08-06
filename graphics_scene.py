from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QPen,
    QPolygonF,
    QAction,
)
from PyQt6.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsLineItem,
    QGraphicsEllipseItem,
    QMenu, QMessageBox,
)

from annotation_items import AnnotationRectItem, AnnotationPolygonItem


class ToolMode:
    RECTANGLE = "rectangle"
    POLYGON = "polygon"


class AnnotationScene(QGraphicsScene):
    annotation_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSceneRect(0, 0, 960, 540)

        self.guide_line = None
        self.hovered_item = None
        self.tool_mode = ToolMode.RECTANGLE

        self.current_label = "court"
        self.current_color = "#00FF00"

        self.available_labels = {
            "court": "#00FF00",
            "net": "#00AAFF",
        }

        self.image_item: Optional[QGraphicsPixmapItem] = None

        self.items_data: List[dict] = []

        # rectangle drawing
        self.start_pos: Optional[QPointF] = None
        self.temp_rect: Optional[AnnotationRectItem] = None

        # polygon drawing
        self.polygon_points: List[QPointF] = []
        self.temp_lines: List[QGraphicsLineItem] = []
        self.temp_vertices: List[QGraphicsEllipseItem] = []

        # image scaling
        self.display_width = 960
        self.display_height = 540
        self.scale_x = 1.0
        self.scale_y = 1.0

    # ---------------------------------------------------------
    # Image
    # ---------------------------------------------------------

    def set_image(self, pixmap):
        self.clear()

        self.items_data.clear()
        self.cancel_polygon()

        self.image_item = self.addPixmap(pixmap)
        self.image_item.setZValue(-100)

        self.setSceneRect(QRectF(pixmap.rect()))

    def set_image_scale(self, original_width: int, original_height: int):
        self.scale_x = original_width / self.display_width
        self.scale_y = original_height / self.display_height

    # ---------------------------------------------------------
    # Tool
    # ---------------------------------------------------------

    def set_tool(self, mode: str):
        self.cancel_polygon()
        self.tool_mode = mode

    def set_current_label(self, label: str, color: str):
        self.current_label = label
        self.current_color = color

    def set_available_labels(self, labels: dict):
        self.available_labels = labels

    # ---------------------------------------------------------
    # Mouse
    # ---------------------------------------------------------

    def mousePressEvent(self, event):
        # Right click removes last polygon point while drawing
        if event.button() == Qt.MouseButton.RightButton:
            if self.tool_mode == ToolMode.POLYGON and self.polygon_points:
                self.remove_last_polygon_point()
                event.accept()
                return

        # If clicking on an existing annotation item,
        # let the item handle the event (selection / dragging)
        clicked_item = self.itemAt(
            event.scenePos(),
            self.views()[0].transform(),
        )

        if isinstance(clicked_item, (AnnotationRectItem, AnnotationPolygonItem)):
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.tool_mode == ToolMode.RECTANGLE:
                self.start_rectangle(event.scenePos())
                event.accept()
                return

            elif self.tool_mode == ToolMode.POLYGON:
                self.add_polygon_point(event.scenePos())
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.temp_rect and self.start_pos:
            rect = QRectF(
                self.start_pos,
                event.scenePos(),
            ).normalized()

            self.temp_rect.setRect(rect)
            event.accept()
            return

            # Polygon guide line
        if self.tool_mode == ToolMode.POLYGON and self.polygon_points:
            last = self.polygon_points[-1]

            if self.guide_line is None:
                pen = QPen(
                    QColor(self.current_color),
                    1,
                    Qt.PenStyle.DashLine,
                )

                self.guide_line = self.addLine(
                    last.x(),
                    last.y(),
                    event.scenePos().x(),
                    event.scenePos().y(),
                    pen,
                )
            else:
                self.guide_line.setLine(
                    last.x(),
                    last.y(),
                    event.scenePos().x(),
                    event.scenePos().y(),
                )

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
                event.button() == Qt.MouseButton.LeftButton
                and self.temp_rect
        ):
            self.finish_rectangle()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.tool_mode == ToolMode.POLYGON:

            if len(self.polygon_points) < 4:
                QMessageBox.warning(
                    self.views()[0],
                    "Invalid polygon",
                    "A polygon must contain at least 4 points.",
                )

                self.cancel_polygon()
                event.accept()
                return

            self.finish_polygon()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)

    # ---------------------------------------------------------
    # Keyboard
    # ---------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_polygon()
            event.accept()
            return

        if event.key() == Qt.Key.Key_Delete:
            self.delete_hovered_item()
            event.accept()
            return

        super().keyPressEvent(event)

    # ---------------------------------------------------------
    # Rectangle
    # ---------------------------------------------------------

    def start_rectangle(self, pos: QPointF):
        self.start_pos = pos
        self.temp_rect = AnnotationRectItem(
            QRectF(pos, pos),
            self.current_color,
            self.current_label,
        )
        self.addItem(self.temp_rect)

    def finish_rectangle(self):
        rect = self.temp_rect.rect()

        self.removeItem(self.temp_rect)

        self.temp_rect = None
        self.start_pos = None

        # Ignore accidental tiny rectangles
        if rect.width() < 5 or rect.height() < 5:
            return

        item = AnnotationRectItem(rect, self.current_color, self.current_label)
        self.addItem(item)

        self.items_data.append(
            {
                "item": item,
                "type": "rectangle",
                "label": self.current_label,
                "color": self.current_color,
            }
        )

        self.annotation_changed.emit()

    # ---------------------------------------------------------
    # Polygon
    # ---------------------------------------------------------

    def add_polygon_point(self, pos: QPointF):
        if self.polygon_points:
            last = self.polygon_points[-1]
            line = self.addLine(
                last.x(),
                last.y(),
                pos.x(),
                pos.y(),
                QPen(QColor(self.current_color), 2),
            )
            self.temp_lines.append(line)

        if self.guide_line:
            self.removeItem(self.guide_line)
            self.guide_line = None

        self.polygon_points.append(pos)

        vertex = self.addEllipse(
            pos.x()-1,
            pos.y()-1,
            2,
            2,
            QPen(Qt.GlobalColor.white, 1),
            QColor(self.current_color),
        )
        self.temp_vertices.append(vertex)

    def remove_last_polygon_point(self):
        if not self.polygon_points:
            return

        self.polygon_points.pop()

        if self.temp_vertices:
            v = self.temp_vertices.pop()
            self.removeItem(v)

        if self.temp_lines:
            l = self.temp_lines.pop()
            self.removeItem(l)

    def finish_polygon(self):

        if self.guide_line:
            self.removeItem(self.guide_line)
            self.guide_line = None

        polygon = QPolygonF(self.polygon_points)

        item = AnnotationPolygonItem(
            polygon,
            self.current_color,
            self.current_label
        )
        self.addItem(item)

        self.items_data.append(
            {
                "item": item,
                "type": "polygon",
                "label": self.current_label,
                "color": self.current_color,
            }
        )

        self.cancel_polygon()

        self.annotation_changed.emit()

    def cancel_polygon(self):
        if self.guide_line:
            self.removeItem(self.guide_line)
            self.guide_line = None

        for line in self.temp_lines:
            self.removeItem(line)

        for vertex in self.temp_vertices:
            self.removeItem(vertex)

        self.temp_lines.clear()
        self.temp_vertices.clear()
        self.polygon_points.clear()

    # ---------------------------------------------------------
    # Hover actions
    # ---------------------------------------------------------

    def set_hovered_item(self, item):
        self.hovered_item = item

    def clear_hovered_item(self, item):
        if self.hovered_item == item:
            self.hovered_item = None


    # ---------------------------------------------------------
    # Context menu
    # ---------------------------------------------------------

    def contextMenuEvent(self, event):
        item = self.itemAt(
            event.scenePos(),
            self.views()[0].transform(),
        )

        if item is None:
            return

        target = None

        for record in self.items_data:
            if record["item"] == item:
                target = record
                break

        if target is None:
            return

        menu = QMenu()

        for label, color in self.available_labels.items():
            action = QAction(label, menu)
            action.triggered.connect(
                lambda checked=False, l=label, c=color: self.change_label(
                    target,
                    l,
                    c,
                )
            )
            menu.addAction(action)

        menu.exec(event.screenPos())

    def change_label(self, target: dict, label: str, color: str):
        target["label"] = label
        target["color"] = color
        target["item"].set_annotation_color(color)

        self.annotation_changed.emit()

    # ---------------------------------------------------------
    # Annotation management
    # ---------------------------------------------------------

    def delete_hovered_item(self):
        if self.hovered_item is None:
            return

        remaining = []

        for record in self.items_data:
            if record["item"] == self.hovered_item:
                self.removeItem(record["item"])
            else:
                remaining.append(record)

        self.items_data = remaining
        self.hovered_item = None

        self.annotation_changed.emit()

    def clear_annotations(self):
        for record in self.items_data:
            self.removeItem(record["item"])

        self.items_data.clear()
        self.cancel_polygon()

        self.annotation_changed.emit()

    def export_annotations(self):
        annotations = []

        for record in self.items_data:
            item = record["item"]

            if record["type"] == "rectangle":
                rect = item.sceneBoundingRect()

                annotations.append(
                    {
                        "type": "rectangle",
                        "label": record["label"],
                        "geometry": {
                            "x": rect.x() * self.scale_x,
                            "y": rect.y() * self.scale_y,
                            "width": rect.width() * self.scale_x,
                            "height": rect.height() * self.scale_y,
                        },
                    }
                )

            elif record["type"] == "polygon":
                poly = item.mapToScene(item.polygon())

                annotations.append(
                    {
                        "type": "polygon",
                        "label": record["label"],
                        "geometry": [
                            [
                                p.x() * self.scale_x,
                                p.y() * self.scale_y,
                            ]
                            for p in poly
                        ],
                    }
                )

        return annotations

    def load_annotations(self, annotations: List[dict]):
        self.clear_annotations()

        for ann in annotations:
            color = self.available_labels.get(
                ann["label"],
                "#00FF00",
            )

            if ann["type"] == "rectangle":
                g = ann["geometry"]

                rect = QRectF(
                    g["x"] / self.scale_x,
                    g["y"] / self.scale_y,
                    g["width"] / self.scale_x,
                    g["height"] / self.scale_y,
                )

                item = AnnotationRectItem(rect, color)
                self.addItem(item)

                self.items_data.append(
                    {
                        "item": item,
                        "type": "rectangle",
                        "label": ann["label"],
                        "color": color,
                    }
                )

            elif ann["type"] == "polygon":
                polygon = QPolygonF(
                    [
                        QPointF(
                            x / self.scale_x,
                            y / self.scale_y,
                        )
                        for x, y in ann["geometry"]
                    ]
                )

                item = AnnotationPolygonItem(polygon, color, ann["label"])
                self.addItem(item)

                self.items_data.append(
                    {
                        "item": item,
                        "type": "polygon",
                        "label": ann["label"],
                        "color": color,
                    }
                )

        self.annotation_changed.emit()

    def import_yolo_result(
            self,
            result,
            job_labels,
            original_width,
            original_height,
    ):
        sx = self.display_width / original_width
        sy = self.display_height / original_height

        # Detection boxes
        if result.boxes is not None:
            for box in result.boxes:
                cls = int(box.cls[0])
                name = result.names[cls].lower()

                if name not in job_labels:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()

                rect = QRectF(
                    x1 * sx,
                    y1 * sy,
                    (x2 - x1) * sx,
                    (y2 - y1) * sy,
                )

                item = AnnotationRectItem(rect, job_labels[name].color, job_labels[name].name)
                self.addItem(item)

                self.items_data.append(
                    {
                        "item": item,
                        "type": "rectangle",
                        "label": job_labels[name].name,
                        "color": job_labels[name].color,
                    }
                )

        # Segmentation masks
        if result.masks is not None:
            for mask, cls in zip(result.masks.xy, result.boxes.cls):
                name = result.names[int(cls)].lower()

                if name not in job_labels:
                    continue

                points = [
                    QPointF(x * sx, y * sy)
                    for x, y in mask
                ]

                polygon = QPolygonF(points)

                item = AnnotationPolygonItem(
                    polygon,
                    job_labels[name].color,
                    job_labels[name].name
                )

                self.addItem(item)

                self.items_data.append(
                    {
                        "item": item,
                        "type": "polygon",
                        "label": job_labels[name].name,
                        "color": job_labels[name].color,
                    }
                )

        self.annotation_changed.emit()
