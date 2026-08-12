"""
Annotation Scene Module

This module provides the main scene for displaying and interacting with annotations
on images. It supports both rectangle and polygon annotations with layer management,
label support, and interaction capabilities including drawing, editing, and deletion.
"""

from __future__ import annotations

from typing import List, Optional, Dict

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

from shape_utils import AnnotationRectItem, AnnotationPolygonItem
from database.db import DatabaseManager
from vb_gui.vb_annotator.database.data import Layer, Label, Annotation


class ToolMode:
    """
    Constants defining the available annotation tools.
    RECTANGLE: Draw rectangular annotations
    POLYGON: Draw polygonal annotations (closed shapes with multiple vertices)
    """
    RECTANGLE = "rectangle"
    POLYGON = "polygon"


class AnnotationScene(QGraphicsScene):
    """
    Main scene class for managing annotations on images.

    This class handles:
    - Displaying images and annotations
    - Creating new annotations (rectangles and polygons)
    - Editing existing annotations
    - Managing layers and labels
    - Importing/exporting annotations
    - Context menus for label changes
    - Keyboard shortcuts for common actions

    Signals:
        annotation_changed: Emitted whenever annotations are added, modified, or deleted
    """

    # Signal emitted when any annotation changes in the scene
    annotation_changed = pyqtSignal()

    def __init__(self, db: DatabaseManager, parent=None):
        """
        Initialize the annotation scene.

        Args:
            db: Database manager instance for accessing annotation data
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.db = db

        # Set default scene size (will be updated when image is loaded)
        self.setSceneRect(0, 0, 960, 540)

        # Polygon drawing state
        self.guide_line = None  # Temporary line showing current polygon edge
        self.hovered_item = None  # Currently hovered annotation item

        # Current tool mode (rectangle or polygon)
        self.tool_mode = ToolMode.RECTANGLE

        # Current layer and label settings for new annotations
        self.current_layer = "court"
        self.current_label = "net"
        self.current_color = "#00FF00"

        # Dictionary mapping layer names to their available labels
        self.layer_labels = self.fetch_db_layers()

        # The background image item
        self.image_item: Optional[QGraphicsPixmapItem] = None

        # Storage for annotation items organized by layer
        self.layer_items = {
            "court": [],  # Court markings and lines
            "players": [],  # Player bounding boxes or segmentation masks
            "ball": [],  # Ball positions
            "actions": [],  # Action annotations (spikes, blocks, etc.)
        }

        # Rectangle drawing state
        self.start_pos: Optional[QPointF] = None  # Starting position of rectangle
        self.temp_rect: Optional[AnnotationRectItem] = None  # Temporary rectangle being drawn

        # Polygon drawing state
        self.polygon_points: List[QPointF] = []  # Points of current polygon
        self.temp_lines: List[QGraphicsLineItem] = []  # Temporary lines between points
        self.temp_vertices: List[QGraphicsEllipseItem] = []  # Temporary vertex markers

        # Image scaling factors for converting between display and original coordinates
        self.display_width = 960
        self.display_height = 540
        self.scale_x = 1.0  # Scale factor from display to original width
        self.scale_y = 1.0  # Scale factor from display to original height

    # ---------------------------------------------------------
    # Image Management
    # ---------------------------------------------------------

    def fetch_db_layers(self) -> Dict[str, List[Label]]:
        """
        Fetch all layers and their associated labels from the database.

        Returns:
            Dictionary mapping layer names to lists of Label objects
        """
        layers = self.db.get_layers()
        return {layer.name: layer.labels for layer in layers}

    def set_layer_labels(self, layer_name: str, labels: List[Label]):
        """
        Update the labels for a specific layer.

        Args:
            layer_name: Name of the layer to update
            labels: List of Label objects for this layer
        """
        self.layer_labels[layer_name] = labels

    def set_current_layer(self, layer_name: str):
        """
        Set the active layer for new annotations.

        Args:
            layer_name: Name of the layer to set as current
        """
        self.current_layer = layer_name

    def set_image(self, pixmap):
        """
        Display a new image in the scene and clear all existing annotations.

        Args:
            pixmap: QPixmap object to display as the background
        """
        # Clear the scene and reset layer storage
        self.clear()
        for key, _ in self.layer_items.items():
            self.layer_items[key].clear()

        # Cancel any ongoing polygon drawing
        self.cancel_polygon()

        # Display the image
        self.image_item = self.addPixmap(pixmap)
        self.image_item.setZValue(-100)  # Ensure image is behind all annotations

        # Update scene rectangle to match image size
        self.setSceneRect(QRectF(pixmap.rect()))

    def set_image_scale(self, original_width: int, original_height: int):
        """
        Set the scaling factors for converting between display and original image coordinates.

        Args:
            original_width: Width of the original image
            original_height: Height of the original image
        """
        self.scale_x = original_width / self.display_width
        self.scale_y = original_height / self.display_height

    # ---------------------------------------------------------
    # Tool Management
    # ---------------------------------------------------------

    def set_tool(self, mode: str):
        """
        Set the active drawing tool.

        Args:
            mode: Tool mode (ToolMode.RECTANGLE or ToolMode.POLYGON)
        """
        # Cancel any ongoing polygon drawing when switching tools
        self.cancel_polygon()
        self.tool_mode = mode

    def set_current_label(self, label: str, color: str):
        """
        Set the active label and color for new annotations.

        Args:
            label: Name of the label
            color: Hex color string for the annotation
        """
        self.current_label = label
        self.current_color = color

    # ---------------------------------------------------------
    # Mouse Event Handling
    # ---------------------------------------------------------

    def mousePressEvent(self, event):
        """
        Handle mouse press events for drawing and interaction.

        - Right click: Remove last polygon point during polygon drawing
        - Left click on annotation: Let the item handle selection
        - Left click on empty space: Start drawing based on current tool
        """
        # Handle right-click to remove last polygon point
        if event.button() == Qt.MouseButton.RightButton:
            if self.tool_mode == ToolMode.POLYGON and self.polygon_points:
                self.remove_last_polygon_point()
                event.accept()
                return

        # If clicking on an existing annotation item, let the item handle it
        clicked_item = self.itemAt(
            event.scenePos(),
            self.views()[0].transform(),
        )

        if isinstance(clicked_item, (AnnotationRectItem, AnnotationPolygonItem)):
            super().mousePressEvent(event)
            return

        # Handle left-click for starting new annotations
        if event.button() == Qt.MouseButton.LeftButton:
            if self.tool_mode == ToolMode.RECTANGLE:
                self.start_rectangle(event.scenePos())
                event.accept()
                return

            elif self.tool_mode == ToolMode.POLYGON:
                self.add_polygon_point(event.scenePos())
                event.accept()
                return

        # Pass unhandled events to parent
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Handle mouse movement for drawing and interaction.

        - Rectangle: Update temporary rectangle size
        - Polygon: Update guide line to show next edge
        """
        # Update temporary rectangle while drawing
        if self.temp_rect and self.start_pos:
            rect = QRectF(
                self.start_pos,
                event.scenePos(),
            ).normalized()

            self.temp_rect.setRect(rect)
            event.accept()
            return

        # Update polygon guide line (shows the edge being drawn)
        if self.tool_mode == ToolMode.POLYGON and self.polygon_points:
            last = self.polygon_points[-1]

            if self.guide_line is None:
                # Create guide line on first movement
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
                # Update existing guide line
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
        """
        Handle mouse release to finish drawing operations.
        """
        if (
                event.button() == Qt.MouseButton.LeftButton
                and self.temp_rect
        ):
            # Finish rectangle drawing
            self.finish_rectangle()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
        Handle double-click to finish polygon drawing.

        Requires at least 4 points for a valid polygon.
        """
        if self.tool_mode == ToolMode.POLYGON:
            # Check if polygon has enough points
            if len(self.polygon_points) < 4:
                QMessageBox.warning(
                    self.views()[0],
                    "Invalid polygon",
                    "A polygon must contain at least 4 points.",
                )

                self.cancel_polygon()
                event.accept()
                return

            # Finish polygon drawing
            self.finish_polygon()
            event.accept()
            return

        super().mouseDoubleClickEvent(event)

    # ---------------------------------------------------------
    # Keyboard Shortcuts
    # ---------------------------------------------------------

    def keyPressEvent(self, event):
        """
        Handle keyboard shortcuts.

        - Escape: Cancel polygon drawing
        - Delete: Delete the currently hovered annotation
        """
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
    # Rectangle Drawing
    # ---------------------------------------------------------

    def start_rectangle(self, pos: QPointF):
        """
        Start drawing a rectangle annotation.

        Args:
            pos: Starting position of the rectangle
        """
        self.start_pos = pos
        self.temp_rect = AnnotationRectItem(
            QRectF(pos, pos),
            self.current_color,
            self.current_label,
        )
        self.temp_rect.set_layer(self.current_layer)
        self.addItem(self.temp_rect)

    def finish_rectangle(self):
        """
        Finish drawing a rectangle annotation.
        Validates the rectangle and adds it to the scene.
        """
        rect = self.temp_rect.rect()

        # Remove temporary rectangle from scene
        self.removeItem(self.temp_rect)
        self.temp_rect = None
        self.start_pos = None

        # Ignore accidental tiny rectangles (minimum 5x5 pixels)
        if rect.width() < 5 or rect.height() < 5:
            return

        # Create permanent rectangle annotation
        item = AnnotationRectItem(rect, self.current_color, self.current_label)
        item.set_layer(self.current_layer)
        self.addItem(item)

        # Store reference in layer management
        self.layer_items[self.current_layer].append(
            {
                "item": item,
                "type": "rectangle",
                "label": self.current_label,
                "color": self.current_color,
            }
        )

        # Notify that annotations have changed
        self.annotation_changed.emit()

    # ---------------------------------------------------------
    # Polygon Drawing
    # ---------------------------------------------------------

    def add_polygon_point(self, pos: QPointF):
        """
        Add a vertex point to the current polygon being drawn.

        Args:
            pos: Position of the new vertex
        """
        # Connect previous point to new point with a line
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

        # Remove existing guide line (will be recreated with new position)
        if self.guide_line:
            self.removeItem(self.guide_line)
            self.guide_line = None

        # Add vertex point
        self.polygon_points.append(pos)

        # Create a small circle marker for the vertex
        vertex = self.addEllipse(
            pos.x() - 1,
            pos.y() - 1,
            2,
            2,
            QPen(Qt.GlobalColor.white, 1),
            QColor(self.current_color),
        )
        self.temp_vertices.append(vertex)

    def remove_last_polygon_point(self):
        """
        Remove the last added polygon point (undo functionality).
        """
        if not self.polygon_points:
            return

        # Remove the point
        self.polygon_points.pop()

        # Remove the vertex marker
        if self.temp_vertices:
            v = self.temp_vertices.pop()
            self.removeItem(v)

        # Remove the connecting line
        if self.temp_lines:
            l = self.temp_lines.pop()
            self.removeItem(l)

    def finish_polygon(self):
        """
        Finish drawing a polygon and add it to the scene.
        Creates a closed polygon from the drawn points.
        """
        # Remove guide line
        if self.guide_line:
            self.removeItem(self.guide_line)
            self.guide_line = None

        # Create the polygon
        polygon = QPolygonF(self.polygon_points)

        # Create permanent polygon annotation
        item = AnnotationPolygonItem(
            polygon,
            self.current_color,
            self.current_label
        )
        item.set_layer(self.current_layer)
        self.addItem(item)

        # Store reference in layer management
        self.layer_items[self.current_layer].append(
            {
                "item": item,
                "type": "polygon",
                "label": self.current_label,
                "color": self.current_color,
            }
        )

        # Clean up temporary drawing elements
        self.cancel_polygon()

        # Notify that annotations have changed
        self.annotation_changed.emit()

    def cancel_polygon(self):
        """
        Cancel the current polygon drawing operation.
        Removes all temporary elements and resets polygon state.
        """
        # Remove guide line
        if self.guide_line:
            self.removeItem(self.guide_line)
            self.guide_line = None

        # Remove all temporary lines
        for line in self.temp_lines:
            self.removeItem(line)

        # Remove all temporary vertices
        for vertex in self.temp_vertices:
            self.removeItem(vertex)

        # Clear temporary storage
        self.temp_lines.clear()
        self.temp_vertices.clear()
        self.polygon_points.clear()

    # ---------------------------------------------------------
    # Hover Management
    # ---------------------------------------------------------

    def set_hovered_item(self, item):
        """
        Set the currently hovered annotation item.

        Args:
            item: The annotation item being hovered
        """
        self.hovered_item = item

    def clear_hovered_item(self, item):
        """
        Clear the hovered state if it matches the given item.

        Args:
            item: The annotation item that is no longer hovered
        """
        if self.hovered_item == item:
            self.hovered_item = None

    # ---------------------------------------------------------
    # Context Menu
    # ---------------------------------------------------------

    def contextMenuEvent(self, event):
        """
        Display a context menu for changing the label of an annotation.

        The menu shows labels that belong to the same layer as the clicked annotation.
        """
        # Find the item at the click position
        item = self.itemAt(
            event.scenePos(),
            self.views()[0].transform(),
        )

        if item is None:
            return

        # Find the annotation record for this item
        target = None
        layer_name = None

        for layer, records in self.layer_items.items():
            for record in records:
                if record["item"] == item:
                    target = record
                    layer_name = layer
                    break

            if target is not None:
                break

        if target is None:
            return

        # Create context menu
        menu = QMenu()

        # Add actions for each label available in this layer
        labels = self.layer_labels.get(layer_name, [])

        for label in labels:
            action = QAction(label.name, menu)

            # Connect action to change_label with the label's info
            action.triggered.connect(
                lambda checked=False,
                       l=label.name,
                       c=label.color,
                       t=target: self.change_label(
                    t,
                    l,
                    c,
                )
            )

            menu.addAction(action)

        # Show the menu
        menu.exec(event.screenPos())

    def change_label(self, target: dict, label: str, color: str):
        """
        Change the label of an existing annotation.

        Args:
            target: The annotation record to modify
            label: New label name
            color: New color for the annotation
        """
        # Update record
        target["label"] = label
        target["color"] = color

        # Update visual appearance
        target["item"].set_annotation_color(color)

        # Notify of change
        self.annotation_changed.emit()

    # ---------------------------------------------------------
    # Annotation Management
    # ---------------------------------------------------------

    def delete_hovered_item(self):
        """
        Delete the currently hovered annotation item.
        """
        if self.hovered_item is None:
            return

        # Get the layer of the hovered item
        layer = self.hovered_item.layer_name

        # Remove item from layer storage
        remaining = []

        for record in self.layer_items[layer]:
            if record["item"] == self.hovered_item:
                self.removeItem(record["item"])
            else:
                remaining.append(record)

        self.layer_items[layer] = remaining

        # Clear hovered state
        self.hovered_item = None

        # Notify of change
        self.annotation_changed.emit()

    def clear_annotations(self, layer_name=None):
        """
        Clear all annotations from the scene.

        Args:
            layer_name: Optional specific layer to clear. If None, clears all layers.
        """
        if layer_name is None:
            # Clear all layers
            for records in self.layer_items.values():
                for record in records:
                    self.removeItem(record["item"])

            # Reset all layer lists
            for key in self.layer_items:
                self.layer_items[key] = []

        else:
            # Clear specific layer
            records = self.layer_items.get(layer_name, [])

            for record in records:
                self.removeItem(record["item"])

            self.layer_items[layer_name] = []

        # Cancel any ongoing drawing
        self.cancel_polygon()

        # Notify of change
        self.annotation_changed.emit()

    def export_annotations(self, layer_name: str, path: str, frame_number: int) -> List[Annotation]:
        """
        Export annotations for a specific layer as database Annotation objects.

        Args:
            layer_name: Name of the layer to export
            path: Media file path associated with these annotations
            frame_number: Frame number (for video annotations)

        Returns:
            List of Annotation objects ready for database storage
        """
        annotations = []

        for record in self.layer_items.get(layer_name, []):
            item = record["item"]

            # Convert geometry to original image coordinates
            if record["type"] == "rectangle":
                rect = item.sceneBoundingRect()
                geometry = {
                    "x": rect.x() * self.scale_x,
                    "y": rect.y() * self.scale_y,
                    "width": rect.width() * self.scale_x,
                    "height": rect.height() * self.scale_y,
                }
            else:  # polygon
                poly = item.mapToScene(item.polygon())
                geometry = [
                    [
                        p.x() * self.scale_x,
                        p.y() * self.scale_y,
                    ]
                    for p in poly
                ]

            # Get layer and label information from database
            layer = self.db.get_layer(layer_name)
            labels = {label.name: label for label in layer.labels}

            # Create Annotation object
            annotations.append(
                Annotation(
                    media_name=path,
                    layer=layer,
                    label=labels[record['label']],
                    frame_number=frame_number,
                    shape_type=record['type'],
                    geometry=geometry
                )
            )

        return annotations

    def load_annotations(
            self,
            annotations: List[Annotation],
            layer_name: str,
    ):
        """
        Load annotations from database objects into the scene.

        Args:
            annotations: List of Annotation objects to load
            layer_name: Name of the layer these annotations belong to
        """
        for ann in annotations:
            # Get label color or use default
            color = ann.label.color if ann.label.color is not None else "#00FF00"

            # Create appropriate annotation item based on shape type
            if ann.shape_type == "rectangle":
                g = ann.geometry

                rect = QRectF(
                    g["x"] / self.scale_x,
                    g["y"] / self.scale_y,
                    g["width"] / self.scale_x,
                    g["height"] / self.scale_y,
                )

                item = AnnotationRectItem(rect, color, ann.label.name)

            elif ann.shape_type == "polygon":
                polygon = QPolygonF(
                    [
                        QPointF(
                            x / self.scale_x,
                            y / self.scale_y,
                        )
                        for x, y in ann.geometry
                    ]
                )

                item = AnnotationPolygonItem(polygon, color, ann.label.name)

            else:
                continue  # Skip unknown shape types

            # Set layer information
            item.layer_name = ann.layer.name

            # Set Z-order based on layer type
            z_values = {
                "court": 0,  # Bottom layer
                "players": 10,  # Middle layer
                "ball": 20,  # Above players
                "actions": 30,  # Top layer
            }
            item.setZValue(z_values.get(layer_name, 0))

            # Add to scene and storage
            self.addItem(item)

            self.layer_items[self.current_layer].append(
                {
                    "item": item,
                    "type": ann.shape_type,
                    "label": ann.label.name,
                    "color": color,
                    "layer": ann.layer.name,
                }
            )

    def import_yolo_result(
            self,
            result,
            layer: Layer,
            original_width: int,
            original_height: int,
    ) -> int:
        """
        Import detections from a YOLO model result.

        Supports both segmentation masks and bounding boxes.

        Args:
            result: YOLO model result object
            layer: Layer object for the annotations
            original_width: Width of the original image
            original_height: Height of the original image

        Returns:
            Number of successfully imported annotations
        """
        # Calculate scale factors from original to display
        sx = self.display_width / original_width
        sy = self.display_height / original_height

        # Create mapping from label names to Label objects
        layer_labels: Dict[str, Label] = {
            label.name.lower(): label
            for label in layer.labels
        }

        imported = 0

        # --------------------------------------------------
        # Import segmentation masks (polygons)
        # --------------------------------------------------
        if result.masks is not None:
            for mask, cls in zip(result.masks.xy, result.boxes.cls):
                name = result.names[int(cls)].lower()

                # Special case: YOLO person detection mapped to player
                if layer.name == 'players':
                    if name == 'person':
                        name = 'player'

                # Skip if label not in this layer
                if name not in layer_labels:
                    continue

                label = layer_labels[name]

                # Convert mask points to polygon
                points = [
                    QPointF(x * sx, y * sy)
                    for x, y in mask
                ]

                polygon = QPolygonF(points)

                # Create and add polygon annotation
                item = AnnotationPolygonItem(
                    polygon,
                    label.color,
                    label.name,
                )

                item.layer_name = layer.name
                self.addItem(item)

                self.layer_items[self.current_layer].append(
                    {
                        "item": item,
                        "type": "polygon",
                        "label": label.name,
                        "color": label.color,
                        "layer": layer.name,
                    }
                )
            imported += 1

        # --------------------------------------------------
        # Import detection boxes (rectangles)
        # --------------------------------------------------
        elif result.boxes is not None:
            for box in result.boxes:
                cls = int(box.cls[0])

                name = result.names[cls].lower()

                # Special case: YOLO person detection mapped to player
                if layer.name == 'players':
                    if name == 'person':
                        name = 'player'

                if name not in layer_labels:
                    continue

                label = layer_labels[name]

                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                rect = QRectF(
                    x1 * sx,
                    y1 * sy,
                    (x2 - x1) * sx,
                    (y2 - y1) * sy,
                )

                # Create and add rectangle annotation
                item = AnnotationRectItem(
                    rect,
                    label.color,
                    label.name,
                )

                item.layer_name = layer.name

                self.addItem(item)

                self.layer_items[self.current_layer].append(
                    {
                        "item": item,
                        "type": "rectangle",
                        "label": label.name,
                        "color": label.color,
                        "layer": layer.name,
                    }
                )

                imported += 1

        # Notify of changes
        self.annotation_changed.emit()

        return imported