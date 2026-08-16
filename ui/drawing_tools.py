from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QFont
from PyQt6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsPolygonItem,
    QGraphicsTextItem,
)
from PyQt6.QtCore import Qt, QPointF, QRectF


class BaseAnnotationItem:
    """
    Base class for all annotation items (rectangles and polygons).
    Provides shared functionality like styling, labels, hover effects, and selection.
    This is an abstract base class meant to be inherited by specific annotation types.
    """

    # Constant size for handle controls (the small squares used for resizing/editing)
    HANDLE_SIZE = 8.0
    # Size when hovering over a handle to make it easier to click
    HANDLE_HOVER_SIZE = 12.0

    def __init__(self):
        """Initialize the base annotation item with default properties."""
        # Layer management for organizing annotations
        self.layer_name = None

        self.annotation_color = QColor('#00FF00')
        self.label = ''

        # Transparency levels for fill colors (40 = ~16% opacity, 80 = ~31% opacity)
        self.fill_alpha = 40
        self.hover_fill_alpha = 80

        # Graphics item for displaying the label text
        self.label_item = None

        # State flags for interaction tracking
        self._editing = False  # Whether the item is being edited
        self._hovering = False  # Whether mouse is hovering over item
        self._active_handle = None  # Which handle is currently being dragged
        self._drag_start = QPointF()  # Starting position for drag operations

        # Enable hover events for this graphics item
        self.setAcceptHoverEvents(True)

    def _setup_style(self, color: str, label: str = ''):
        """
        Set up the visual style of the annotation.

        Args:
            color: Hex color string (e.g., '#FF0000' for red)
            label: Text label to display on the annotation
        """
        # Store the annotation color and label
        self.annotation_color = QColor(color)
        self.label = label

        # Set transparency levels (can be overridden by subclasses)
        self.fill_alpha = 40
        self.hover_fill_alpha = 80

        # Create pens for different states (normal, hover, selected)
        # Normal: 2px solid line with annotation color
        self.normal_pen = QPen(self.annotation_color, 2)
        # Hover: 3px lighter version of the annotation color
        self.hover_pen = QPen(self.annotation_color.lighter(150), 3)
        # Selected: 3px golden yellow line
        self.selected_pen = QPen(QColor('#FFD54A'), 3)

        # Create brushes for fill colors with transparency
        # Normal brush: annotation color with low opacity
        self.normal_brush = QBrush(
            QColor(
                self.annotation_color.red(),
                self.annotation_color.green(),
                self.annotation_color.blue(),
                self.fill_alpha,
            )
        )

        # Hover brush: annotation color with higher opacity for better visibility
        self.hover_brush = QBrush(
            QColor(
                self.annotation_color.red(),
                self.annotation_color.green(),
                self.annotation_color.blue(),
                self.hover_fill_alpha,
            )
        )

        # Set up the label text item
        self._setup_label()

    def _setup_label(self):
        """
        Create and configure the label text item.
        Removes existing label if present and creates a new one with HTML styling.
        """
        # Clean up existing label if it exists
        if hasattr(self, 'label_item') and self.label_item:
            if self.label_item.scene():
                self.label_item.scene().removeItem(self.label_item)

        # If no label text, remove label item
        if not self.label:
            self.label_item = None
            return

        # Create a new text item with the label
        self.label_item = QGraphicsTextItem(self.label, self)
        # Set text color to white
        self.label_item.setDefaultTextColor(Qt.GlobalColor.white)
        # Set font: Arial, size 10, bold
        self.label_item.setFont(QFont('Arial', 10, QFont.Weight.Bold))

        # Use HTML for styling: dark semi-transparent background with rounded corners
        self.label_item.setHtml(
            f'<div style="background-color: rgba(0,0,0,160); '
            f'padding: 2px 6px; border-radius: 3px;">'
            f'{self.label}</div>'
        )

        # Position the label above the annotation
        self._update_label_position()
        # Ensure label appears on top of other items
        self.label_item.setZValue(1000)

    def _update_label_position(self):
        """
        Update the position of the label.
        This method is meant to be overridden by subclasses to position labels appropriately.
        """
        pass  # Implemented in subclasses

    def _apply_normal(self):
        """Apply the normal (non-interactive) visual state to the annotation."""
        self.setPen(self.normal_pen)
        self.setBrush(self.normal_brush)

        # Set label text to white
        if self.label_item:
            self.label_item.setDefaultTextColor(Qt.GlobalColor.white)

        # Trigger a repaint
        self.update()

    def _apply_hover(self):
        """Apply the hover visual state when mouse is over the annotation."""
        self.setPen(self.hover_pen)
        self.setBrush(self.hover_brush)

        # Highlight label text in yellow during hover
        if self.label_item:
            self.label_item.setDefaultTextColor(Qt.GlobalColor.yellow)

        self.update()

    def _apply_selected(self):
        """Apply the selected visual state when annotation is selected."""
        self.setPen(self.selected_pen)
        self.setBrush(self.hover_brush)  # Use hover brush for better visibility

        # Highlight label text in yellow when selected
        if self.label_item:
            self.label_item.setDefaultTextColor(Qt.GlobalColor.yellow)

        self.update()

    def set_label(self, label: str):
        """
        Update the annotation's label text.

        Args:
            label: New label text
        """
        self.label = label
        self._setup_label()  # Recreate label with new text

    def set_annotation_color(self, color: str):
        """
        Change the annotation's color and update all visual aspects.

        Args:
            color: New hex color string
        """
        # Rebuild style with new color while keeping existing label
        self._setup_style(color, self.label)

        # Apply appropriate visual state based on current interaction state
        if self.isSelected():
            self._apply_selected()
        elif self._hovering:
            self._apply_hover()
        else:
            self._apply_normal()

    def set_layer(self, layer_name: str):
        """
        Assign the annotation to a specific layer for organizational purposes.

        Args:
            layer_name: Name of the layer
        """
        self.layer_name = layer_name

    def _handle_rect(self, center: QPointF) -> QRectF:
        """
        Create a rectangle for a handle at a specific center point.
        Handles are the small squares used for resizing/editing.

        Args:
            center: Center point of the handle

        Returns:
            QRectF: Rectangle representing the handle area
        """
        s = self.HANDLE_SIZE
        return QRectF(center.x() - s / 2, center.y() - s / 2, s, s)

    def _draw_handle(self, painter, center: QPointF, active=False):
        """
        Draw a single handle control at the specified position.

        Args:
            painter: QPainter instance for drawing
            center: Center point of the handle
            active: Whether this handle is currently being interacted with
        """
        rect = self._handle_rect(center)

        # White outline for the handle
        painter.setPen(QPen(Qt.GlobalColor.white, 1))

        # Fill color: golden yellow if active, otherwise annotation color
        if active:
            painter.setBrush(QBrush(QColor('#FFD54A')))
        else:
            painter.setBrush(QBrush(self.annotation_color))

        # Draw the handle as a filled rectangle
        painter.drawRect(rect)

    def _notify_geometry_changed(self):
        """
        Notify the scene that the annotation's geometry has changed.
        This triggers updates to the label position and emits a signal if available.
        """
        # Update label position and trigger repaint
        self._update_label_position()
        self.update()

        # If the item is in a scene, try to emit a change signal
        if self.scene():
            try:
                self.scene().annotation_changed.emit()
            except Exception:
                pass  # Signal might not exist on the scene

    def _update_visual_state(self):
        """
        Update the visual appearance based on current state (selected, hovered, or normal).
        This ensures the annotation always displays the correct styling.
        """
        if self.isSelected():
            self._apply_selected()
        elif self._hovering:
            self._apply_hover()
        else:
            self._apply_normal()


class AnnotationRectItem(QGraphicsRectItem, BaseAnnotationItem):
    """
    Rectangular annotation item that can be resized using handles.
    Inherits from both QGraphicsRectItem (for rectangle functionality) and BaseAnnotationItem (for annotation features).
    """

    # Handle identifiers for different corners and edges of the rectangle
    HANDLE_NONE = -1
    HANDLE_TOP_LEFT = 0
    HANDLE_TOP = 1
    HANDLE_TOP_RIGHT = 2
    HANDLE_RIGHT = 3
    HANDLE_BOTTOM_RIGHT = 4
    HANDLE_BOTTOM = 5
    HANDLE_BOTTOM_LEFT = 6
    HANDLE_LEFT = 7

    # Minimum size to prevent the rectangle from becoming too small
    MIN_SIZE = 5.0

    def __init__(self, rect, color: str, label: str = ''):
        """
        Initialize a rectangular annotation.

        Args:
            rect: QRectF defining the rectangle's geometry
            color: Hex color string for the annotation
            label: Text label for the annotation
        """
        # Initialize both parent classes
        QGraphicsRectItem.__init__(self, rect)
        BaseAnnotationItem.__init__(self)

        # Set up visual style
        self._setup_style(color, label)
        self._apply_normal()

        # Enable interaction flags
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # State for resize operations
        self._resizing = False
        self._active_handle = self.HANDLE_NONE

    def _update_label_position(self):
        """
        Position the label centered above the rectangle.
        Overrides the base class method.
        """
        if self.label_item:
            r = self.rect()
            # Calculate center position and offset above the rectangle
            label_width = self.label_item.boundingRect().width()
            x = r.x() + (r.width() - label_width) / 2
            y = r.y() - self.label_item.boundingRect().height() - 4
            self.label_item.setPos(QPointF(x, y))

    def _handle_points(self):
        """
        Get all handle positions for the rectangle.

        Returns:
            dict: Mapping of handle identifiers to their QPointF positions
        """
        r = self.rect()

        return {
            self.HANDLE_TOP_LEFT: r.topLeft(),
            self.HANDLE_TOP: QPointF(r.center().x(), r.top()),
            self.HANDLE_TOP_RIGHT: r.topRight(),
            self.HANDLE_RIGHT: QPointF(r.right(), r.center().y()),
            self.HANDLE_BOTTOM_RIGHT: r.bottomRight(),
            self.HANDLE_BOTTOM: QPointF(r.center().x(), r.bottom()),
            self.HANDLE_BOTTOM_LEFT: r.bottomLeft(),
            self.HANDLE_LEFT: QPointF(r.left(), r.center().y()),
        }

    def _handle_at(self, pos: QPointF):
        """
        Find which handle is at a given position.

        Args:
            pos: Position to check

        Returns:
            int: Handle identifier or HANDLE_NONE if no handle at position
        """
        for handle, point in self._handle_points().items():
            if self._handle_rect(point).contains(pos):
                return handle
        return self.HANDLE_NONE

    def _cursor_for_handle(self, handle):
        """
        Get the appropriate cursor shape for each handle type.

        Args:
            handle: Handle identifier

        Returns:
            Qt.CursorShape: Appropriate cursor for the handle
        """
        mapping = {
            # Diagonal resize cursors for corners
            self.HANDLE_TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
            self.HANDLE_BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            self.HANDLE_TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
            self.HANDLE_BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
            # Vertical resize cursors for top and bottom edges
            self.HANDLE_TOP: Qt.CursorShape.SizeVerCursor,
            self.HANDLE_BOTTOM: Qt.CursorShape.SizeVerCursor,
            # Horizontal resize cursors for left and right edges
            self.HANDLE_LEFT: Qt.CursorShape.SizeHorCursor,
            self.HANDLE_RIGHT: Qt.CursorShape.SizeHorCursor,
        }
        return mapping.get(handle, Qt.CursorShape.ArrowCursor)

    def hoverEnterEvent(self, event):
        """Handle mouse entering the annotation area."""
        self._hovering = True

        # Notify the scene that this item is being hovered
        if self.scene():
            self.scene().set_hovered_item(self)

        self._update_visual_state()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        """Handle mouse movement while hovering over the annotation."""
        if self.isSelected():
            # Check if cursor is over a handle
            handle = self._handle_at(event.pos())

            if handle != self.HANDLE_NONE:
                # Change cursor to appropriate resize cursor
                self.setCursor(self._cursor_for_handle(handle))
            else:
                # Change cursor to move cursor for dragging
                self.setCursor(Qt.CursorShape.SizeAllCursor)

        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle mouse leaving the annotation area."""
        self._hovering = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Notify the scene that hover has ended
        if self.scene():
            self.scene().clear_hovered_item(self)

        self._update_visual_state()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press events for starting resize or drag operations."""
        if self.isSelected():
            # Check if pressing on a handle
            handle = self._handle_at(event.pos())

            if handle != self.HANDLE_NONE:
                # Start resize operation
                self._resizing = True
                self._active_handle = handle
                event.accept()
                return

        # If not resizing, pass to parent for standard behavior (selection/drag)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse movement during resize or drag operations."""
        if self._resizing:
            # Resize the rectangle based on handle being dragged
            r = QRectF(self.rect())
            p = event.pos()

            # Left side handles (affect left edge)
            if self._active_handle in (
                    self.HANDLE_TOP_LEFT,
                    self.HANDLE_LEFT,
                    self.HANDLE_BOTTOM_LEFT,
            ):
                r.setLeft(min(p.x(), r.right() - self.MIN_SIZE))

            # Right side handles (affect right edge)
            if self._active_handle in (
                    self.HANDLE_TOP_RIGHT,
                    self.HANDLE_RIGHT,
                    self.HANDLE_BOTTOM_RIGHT,
            ):
                r.setRight(max(p.x(), r.left() + self.MIN_SIZE))

            # Top side handles (affect top edge)
            if self._active_handle in (
                    self.HANDLE_TOP_LEFT,
                    self.HANDLE_TOP,
                    self.HANDLE_TOP_RIGHT,
            ):
                r.setTop(min(p.y(), r.bottom() - self.MIN_SIZE))

            # Bottom side handles (affect bottom edge)
            if self._active_handle in (
                    self.HANDLE_BOTTOM_LEFT,
                    self.HANDLE_BOTTOM,
                    self.HANDLE_BOTTOM_RIGHT,
            ):
                r.setBottom(max(p.y(), r.top() + self.MIN_SIZE))

            # Apply the new rectangle geometry
            self.prepareGeometryChange()
            self.setRect(r.normalized())  # Normalize ensures positive width/height
            self._update_label_position()
            self.update()

            event.accept()
            return

        # If not resizing, pass to parent for drag movement
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release after resize or drag operations."""
        if self._resizing:
            # End resize operation
            self._resizing = False
            self._active_handle = self.HANDLE_NONE
            # Notify about geometry change
            self._notify_geometry_changed()
            event.accept()
            return

        # If not resizing, pass to parent
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """
        Handle changes to the item's state (selection, position, etc.).
        This is called by Qt when various properties change.
        """
        if change == QGraphicsRectItem.GraphicsItemChange.ItemSelectedHasChanged:
            # Update visual state when selection changes
            self._update_visual_state()

        elif change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update label position when item is moved
            self._update_label_position()

        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        """
        Custom painting method for the rectangle annotation.
        Draws the rectangle and handles when selected.
        """
        # Enable anti-aliasing for smoother edges
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the main rectangle
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

        # Draw handles if the item is selected
        if self.isSelected():
            for handle, point in self._handle_points().items():
                self._draw_handle(
                    painter,
                    point,
                    active=(handle == self._active_handle),
                )


class AnnotationPolygonItem(QGraphicsPolygonItem, BaseAnnotationItem):
    """
    Polygon annotation item with editable vertices.
    Inherits from QGraphicsPolygonItem (for polygon functionality) and BaseAnnotationItem (for annotation features).
    """

    def __init__(self, polygon, color: str, label: str = ''):
        """
        Initialize a polygon annotation.

        Args:
            polygon: QPolygonF defining the polygon's vertices
            color: Hex color string for the annotation
            label: Text label for the annotation
        """
        # Initialize both parent classes
        QGraphicsPolygonItem.__init__(self, polygon)
        BaseAnnotationItem.__init__(self)

        # Set up visual style
        self._setup_style(color, label)
        self._apply_normal()

        # Enable interaction flags
        self.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsPolygonItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        # State for vertex editing
        self._editing_vertex = False  # Whether a vertex is being edited
        self._active_vertex = -1  # Index of the vertex being edited

    def _update_label_position(self):
        """
        Position the label centered above the polygon's bounding box.
        Overrides the base class method.
        """
        if self.label_item:
            bounds = self.boundingRect()
            # Calculate center position and offset above the polygon
            label_width = self.label_item.boundingRect().width()
            x = bounds.x() + (bounds.width() - label_width) / 2
            y = bounds.y() - self.label_item.boundingRect().height() - 4
            self.label_item.setPos(QPointF(x, y))

    def _vertex_at(self, pos: QPointF):
        """
        Find which vertex is at a given position.

        Args:
            pos: Position to check

        Returns:
            int: Index of the vertex, or -1 if no vertex at position
        """
        poly = self.polygon()

        for i in range(poly.count()):
            if self._handle_rect(poly[i]).contains(pos):
                return i

        return -1

    def hoverEnterEvent(self, event):
        """Handle mouse entering the annotation area."""
        self._hovering = True

        # Notify the scene that this item is being hovered
        if self.scene():
            self.scene().set_hovered_item(self)

        self._update_visual_state()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        """Handle mouse movement while hovering over the annotation."""
        if self.isSelected():
            # Check if cursor is over a vertex
            idx = self._vertex_at(event.pos())

            if idx >= 0:
                # Show crosshair cursor for vertex editing
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                # Show move cursor for dragging the polygon
                self.setCursor(Qt.CursorShape.SizeAllCursor)

        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle mouse leaving the annotation area."""
        self._hovering = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Notify the scene that hover has ended
        if self.scene():
            self.scene().clear_hovered_item(self)

        self._update_visual_state()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press events for starting vertex editing or drag operations."""
        if self.isSelected():
            # Check if pressing on a vertex
            idx = self._vertex_at(event.pos())

            if idx >= 0:
                # Start vertex editing operation
                self._editing_vertex = True
                self._active_vertex = idx
                event.accept()
                return

        # If not editing vertex, pass to parent for standard behavior
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse movement during vertex editing or drag operations."""
        if self._editing_vertex:
            # Move the active vertex to the current mouse position
            poly = self.polygon()
            poly[self._active_vertex] = event.pos()

            # Apply the updated polygon
            self.prepareGeometryChange()
            self.setPolygon(poly)

            # Update label position and repaint
            self._update_label_position()
            self.update()

            event.accept()
            return

        # If not editing vertex, pass to parent for drag movement
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release after vertex editing or drag operations."""
        if self._editing_vertex:
            # End vertex editing operation
            self._editing_vertex = False
            self._active_vertex = -1
            # Notify about geometry change
            self._notify_geometry_changed()
            event.accept()
            return

        # If not editing vertex, pass to parent
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """
        Handle changes to the item's state (selection, position, etc.).
        This is called by Qt when various properties change.
        """
        if change == QGraphicsPolygonItem.GraphicsItemChange.ItemSelectedHasChanged:
            # Update visual state when selection changes
            self._update_visual_state()

        elif change == QGraphicsPolygonItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update label position when item is moved
            self._update_label_position()

        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        """
        Custom painting method for the polygon annotation.
        Draws the polygon, vertices, and handles when selected.
        """
        # Enable anti-aliasing for smoother edges
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the main polygon
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawPolygon(self.polygon())

        # Draw small circles at each vertex for visibility
        painter.setBrush(QBrush(self.annotation_color))
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        for point in self.polygon():
            painter.drawEllipse(point, 2, 2)

        # Draw resize handles at each vertex if selected
        if self.isSelected():
            poly = self.polygon()
            for i in range(poly.count()):
                self._draw_handle(
                    painter,
                    poly[i],
                    active=(i == self._active_vertex),
                )