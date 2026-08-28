"""
Undo/Redo command classes for annotation editing.

These commands operate on plain QGraphicsItem-like objects
(AnnotationRectItem / AnnotationPolygonItem) via duck typing,
so this module has no dependency on drawing_tools.py and avoids
any circular imports.

Undo history is intentionally scoped to "whatever is currently
loaded in the scene" — the owning AnnotationScene clears its
QUndoStack whenever annotations are torn down and reloaded
(new frame, new image, layer switch), since old commands would
otherwise reference QGraphicsItems that no longer exist.
"""

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QUndoCommand, QPolygonF


class MoveItemCommand(QUndoCommand):
    """Undo/redo for dragging (translating) an annotation item."""

    ID = 1001

    def __init__(self, item, old_pos: QPointF, new_pos: QPointF, description="Move annotation"):
        super().__init__(description)
        self.item = item
        self.old_pos = QPointF(old_pos)
        self.new_pos = QPointF(new_pos)

    def undo(self):
        self.item.setPos(self.old_pos)
        self.item._notify_geometry_changed()

    def redo(self):
        self.item.setPos(self.new_pos)
        self.item._notify_geometry_changed()

    def id(self):
        # Enables mergeWith() so consecutive small drags of the
        # same item collapse into a single undo step.
        return self.ID

    def mergeWith(self, other):
        if other.id() != self.id() or other.item is not self.item:
            return False
        self.new_pos = other.new_pos
        return True


class ResizeRectCommand(QUndoCommand):
    """Undo/redo for resizing a rectangle annotation via its handles."""

    def __init__(self, item, old_rect: QRectF, new_rect: QRectF, description="Resize annotation"):
        super().__init__(description)
        self.item = item
        self.old_rect = QRectF(old_rect)
        self.new_rect = QRectF(new_rect)

    def undo(self):
        self.item.prepareGeometryChange()
        self.item.setRect(self.old_rect)
        self.item._notify_geometry_changed()

    def redo(self):
        self.item.prepareGeometryChange()
        self.item.setRect(self.new_rect)
        self.item._notify_geometry_changed()


class EditPolygonCommand(QUndoCommand):
    """Undo/redo for dragging a single polygon vertex."""

    def __init__(self, item, old_polygon: QPolygonF, new_polygon: QPolygonF, description="Edit polygon vertex"):
        super().__init__(description)
        self.item = item
        self.old_polygon = QPolygonF(old_polygon)
        self.new_polygon = QPolygonF(new_polygon)

    def undo(self):
        self.item.prepareGeometryChange()
        self.item.setPolygon(self.old_polygon)
        self.item._notify_geometry_changed()

    def redo(self):
        self.item.prepareGeometryChange()
        self.item.setPolygon(self.new_polygon)
        self.item._notify_geometry_changed()


class DeleteAnnotationCommand(QUndoCommand):
    """
    Undo/redo for removing an annotation item from the scene.

    `record` is the same dict AnnotationScene stores in
    `layer_items[layer_name]` (keys: item/type/label/color), so
    undo re-inserts the exact same record rather than rebuilding it.
    """

    def __init__(self, scene, record: dict, layer_name: str, description="Delete annotation"):
        super().__init__(description)
        self.scene = scene
        self.record = record
        self.layer_name = layer_name

    def undo(self):
        self.scene.addItem(self.record["item"])
        self.scene.layer_items[self.layer_name].append(self.record)
        self.scene.annotation_changed.emit()

    def redo(self):
        self.scene.removeItem(self.record["item"])
        if self.record in self.scene.layer_items[self.layer_name]:
            self.scene.layer_items[self.layer_name].remove(self.record)

        if self.scene.hovered_item is self.record["item"]:
            self.scene.hovered_item = None

        self.scene.annotation_changed.emit()


class CreateAnnotationCommand(QUndoCommand):
    """Undo/redo for creating a new annotation (rectangle or polygon)."""

    def __init__(self, scene, record: dict, layer_name: str, description="Create annotation"):
        super().__init__(description)
        self.scene = scene
        self.record = record
        self.layer_name = layer_name

    def undo(self):
        self.scene.removeItem(self.record["item"])
        if self.record in self.scene.layer_items[self.layer_name]:
            self.scene.layer_items[self.layer_name].remove(self.record)
        if self.scene.hovered_item is self.record["item"]:
            self.scene.hovered_item = None
        self.scene.annotation_changed.emit()

    def redo(self):
        # item.scene() is None after an undo() call above; re-attach it
        if self.record["item"].scene() is None:
            self.scene.addItem(self.record["item"])
        if self.record not in self.scene.layer_items[self.layer_name]:
            self.scene.layer_items[self.layer_name].append(self.record)
        self.scene.annotation_changed.emit()


class ChangeLabelCommand(QUndoCommand):
    """Undo/redo for changing an annotation's label/color via the context menu."""

    def __init__(self, scene, record: dict, old_label: str, old_color: str,
                 new_label: str, new_color: str, description="Change annotation label"):
        super().__init__(description)
        self.scene = scene
        self.record = record
        self.old_label = old_label
        self.old_color = old_color
        self.new_label = new_label
        self.new_color = new_color

    def _apply(self, label, color):
        self.record["label"] = label
        self.record["color"] = color
        self.record["item"].update_annotation(label, color)
        self.scene.annotation_changed.emit()

    def undo(self):
        self._apply(self.old_label, self.old_color)

    def redo(self):
        self._apply(self.new_label, self.new_color)
