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
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QUndoCommand, QPolygonF

from vb_gui.vb_annotator.database.data import Label, Annotation, Layer


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
    Undo/redo for removing an annotation. If the record has already been
    persisted (annotation_id set — true for AI imports immediately, and
    for manual draws after a Ctrl+S), the underlying DB row is deleted on
    redo() and precisely restored on undo(), so the deletion actually
    survives a layer/frame reload instead of only affecting the in-memory
    scene. Records that were never saved (fresh manual draws) have no
    annotation_id, so no DB action happens for them — nothing to sync.
    """

    def __init__(self, scene, record: dict, layer_name: str,
                 media_path, media_type, width, height, frame_number, layer: Layer,
                 description="Delete annotation"):
        super().__init__(description)
        self.scene = scene
        self.record = record
        self.layer_name = layer_name
        self.media_path = media_path
        self.media_type = media_type
        self.width = width
        self.height = height
        self.frame_number = frame_number
        self.layer = layer

    def _label_object(self) -> Optional[Label]:
        return next((l for l in self.layer.labels if l.name == self.record["label"]), None)

    def _geometry_for_item(self):
        item = self.record["item"]
        if self.record["type"] == "rectangle":
            rect = item.sceneBoundingRect()
            return {
                "x": rect.x() * self.scene.scale_x, "y": rect.y() * self.scene.scale_y,
                "width": rect.width() * self.scene.scale_x, "height": rect.height() * self.scene.scale_y,
            }
        poly = item.mapToScene(item.polygon())
        return [[p.x() * self.scene.scale_x, p.y() * self.scene.scale_y] for p in poly]

    def undo(self):
        self.scene.addItem(self.record["item"])
        self.scene.layer_items[self.layer_name].append(self.record)

        if self.record.get("annotation_id") is not None and self.media_path is not None:
            label = self._label_object()
            if label is not None:
                ann = Annotation(
                    media_name=self.media_path, layer=self.layer, label=label,
                    frame_number=self.frame_number, shape_type=self.record["type"],
                    geometry=self._geometry_for_item(),
                    is_ai_generated=self.record.get("is_ai_generated", False),
                    confirmed=self.record.get("confirmed", True),
                )
                new_id = self.scene.db.insert_annotation(
                    self.media_path, self.media_type, self.width, self.height,
                    self.layer, self.frame_number, ann,
                )
                self.record["annotation_id"] = new_id

        self.scene.annotation_changed.emit()
        self.scene._unconfirm_frame_for_layer(self.layer_name)

    def redo(self):
        self.scene.removeItem(self.record["item"])
        if self.record in self.scene.layer_items[self.layer_name]:
            self.scene.layer_items[self.layer_name].remove(self.record)
        if self.scene.hovered_item is self.record["item"]:
            self.scene.hovered_item = None

        if self.record.get("annotation_id") is not None:
            self.scene.db.delete_annotations_by_ids([self.record["annotation_id"]])
            self.record["annotation_id"] = None

        self.scene.annotation_changed.emit()
        self.scene._unconfirm_frame_for_layer(self.layer_name)


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
        self.scene._unconfirm_frame_for_layer(self.layer_name)

    def redo(self):
        # item.scene() is None after an undo() call above; re-attach it
        if self.record["item"].scene() is None:
            self.scene.addItem(self.record["item"])
        if self.record not in self.scene.layer_items[self.layer_name]:
            self.scene.layer_items[self.layer_name].append(self.record)
        self.scene.annotation_changed.emit()
        self.scene._unconfirm_frame_for_layer(self.layer_name)


class ChangeLabelCommand(QUndoCommand):
    """Undo/redo for a context-menu label/color change. Syncs to the DB
    immediately when the row has already been persisted, for the same
    reason as DeleteAnnotationCommand above."""

    def __init__(self, scene, record: dict, old_label, old_color, new_label, new_color,
                 description="Change annotation label"):
        super().__init__(description)
        self.scene = scene
        self.record = record
        self.old_label, self.old_color = old_label, old_color
        self.new_label, self.new_color = new_label, new_color

    def _apply(self, label, color):
        self.record["label"] = label
        self.record["color"] = color
        self.record["item"].update_annotation(label, color)

        layer_name = self.record["item"].layer_name
        if self.record.get("annotation_id") is not None and layer_name is not None:
            layer = self.scene.db.get_layer(layer_name)
            label_obj = next((l for l in layer.labels if l.name == label), None) if layer else None
            if label_obj is not None:
                self.scene.db.update_annotation_label(self.record["annotation_id"], label_obj.label_id)

        self.scene.annotation_changed.emit()
        self.scene._unconfirm_frame_for_layer(layer_name)

    def undo(self):
        self._apply(self.old_label, self.old_color)

    def redo(self):
        self._apply(self.new_label, self.new_color)


class BulkCreateAnnotationCommand(QUndoCommand):
    """
    Undo/redo for a batch of AI-generated annotations (e.g. one YOLO run).

    The source of truth is the DB, not an in-memory geometry cache:
      - redo() inserts the batch via db.insert_ai_annotations() and adds
        the corresponding scene items.
      - undo() deletes exactly those DB rows by id and removes the scene
        items — it can never touch a row a human confirmed/edited since,
        because it only ever references the ids this command itself created.

    A single Ctrl+Z removes the whole AI batch as one step, as long as it's
    still on top of the undo stack for the current frame.
    """

    def __init__(self, scene, db, layer_name, media_path, media_type, width, height,
                 frame_number, layer, records, annotations_for_db,
                 description="AI batch import"):
        super().__init__(description)
        self.scene = scene
        self.db = db
        self.layer_name = layer_name
        self.media_path = media_path
        self.media_type = media_type
        self.width = width
        self.height = height
        self.frame_number = frame_number
        self.layer = layer
        self.records = records  # scene dict records {item, type, label, color, ...}
        self.annotations_for_db = annotations_for_db  # Annotation dataclasses (no id yet)
        self.db_ids = None

    def redo(self):
        # Insert (or re-insert, after a prior undo) and remember the ids
        self.db_ids = self.db.insert_ai_annotations(
            self.media_path, self.media_type, self.width, self.height,
            self.layer, self.frame_number, self.annotations_for_db,
        )
        for record, db_id in zip(self.records, self.db_ids):
            record["annotation_id"] = db_id
            if record["item"].scene() is None:
                self.scene.addItem(record["item"])
            if record not in self.scene.layer_items[self.layer_name]:
                self.scene.layer_items[self.layer_name].append(record)

        self.scene.annotation_changed.emit()
        self.scene._unconfirm_frame_for_layer(self.layer_name)

    def undo(self):
        if self.db_ids:
            self.db.delete_annotations_by_ids(self.db_ids)

        for record in self.records:
            self.scene.removeItem(record["item"])
            if record in self.scene.layer_items[self.layer_name]:
                self.scene.layer_items[self.layer_name].remove(record)
            record["annotation_id"] = None
            if self.scene.hovered_item is record["item"]:
                self.scene.hovered_item = None

        self.scene.annotation_changed.emit()
        self.scene._unconfirm_frame_for_layer(self.layer_name)
