from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF, QTransform
from PyQt6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem,
                             QGraphicsLineItem, QGraphicsPolygonItem,
                             QGraphicsSimpleTextItem)

from src.vb_gui.vb_annotator.database.court_calibration import (CALIBRATION_STEPS,
                                                                STEP_BY_KEY,
                                                                order_polygon_clockwise,
                                                                compute_point_labels)

HANDLE_RADIUS = 5
LABEL_OFFSET = QPointF(8, -10)


class _Handle(QGraphicsEllipseItem):
    def __init__(self, overlay, key, index, color):
        r = HANDLE_RADIUS
        super().__init__(-r, -r, 2 * r, 2 * r)
        self._overlay, self._key, self._index = overlay, key, index
        self._ready = False
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(Qt.GlobalColor.black, 1))
        self.setZValue(1000)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self._ready:
            self._overlay._handle_moved(self._key, self._index, value)
        return super().itemChange(change, value)


class CalibrationOverlay:
    """
    Owns the court-calibration shapes. Points are stored in ORIGINAL image
    pixels and converted to display coords with scene.scale_x/scale_y, so
    they survive any change of display scale.
    """

    def __init__(self, scene):
        self.scene = scene
        self.media_path: Optional[str] = None
        self.dirty = False
        self.active_key: Optional[str] = None
        self.on_changed: Optional[Callable[[], None]] = None
        self.on_step_completed: Optional[Callable[[str], None]] = None

        self._visible = False
        self._points: Dict[str, List[List[float]]] = {}
        self._finished_open = set()  # open-ended polygons (net) the user closed
        self._shape_items: Dict[str, QGraphicsItem] = {}
        self._handles: Dict[str, List[_Handle]] = {}
        self._labels: Dict[str, List[QGraphicsSimpleTextItem]] = {}
        self._guide = None

    # ---------------- state ----------------

    def _is_complete(self, key) -> bool:
        pts = self._points.get(key, [])
        step = STEP_BY_KEY[key]
        if step.points is not None:
            return len(pts) >= step.points
        return len(pts) >= 3 and key in self._finished_open

    def completion(self) -> Dict[str, bool]:
        return {s.key: self._is_complete(s.key) for s in CALIBRATION_STEPS}

    def export(self) -> dict:
        return {k: [list(p) for p in pts] for k, pts in self._points.items()
                if self._is_complete(k)}

    def set_active_step(self, key):
        self.active_key = key
        self._clear_guide()

    def set_visible(self, visible: bool):
        self._visible = visible
        self.rebuild_items()

    def _mark_dirty(self):
        self.dirty = True
        if self.on_changed:
            self.on_changed()

    # ---------------- load / clear ----------------

    def load(self, media_path, calibration: Optional[dict]):
        self._drop_all_items()
        self.media_path = media_path
        self._points, self._finished_open = {}, set()
        for key, pts in (calibration or {}).items():
            if key in STEP_BY_KEY:
                self._points[key] = [[float(x), float(y)] for x, y in pts]
                if STEP_BY_KEY[key].points is None:
                    self._finished_open.add(key)
        self.dirty = False
        self.rebuild_items()
        if self.on_changed:
            self.on_changed()

    def clear(self, key):
        self._points.pop(key, None)
        self._finished_open.discard(key)
        self._redraw(key)
        self._mark_dirty()

    def clear_all(self):
        for key in list(self._points):
            self._points.pop(key, None)
            self._redraw(key)
        self._finished_open.clear()
        self._mark_dirty()

    # ---------------- input (called from the scene) ----------------

    def handle_press(self, scene_pos: QPointF, button) -> bool:
        """True = event consumed (a point was added). False = let the
        scene handle it (e.g. dragging an existing handle)."""
        if not self._visible or self.active_key is None:
            return False
        if isinstance(self.scene.itemAt(scene_pos, QTransform()), _Handle):
            return False
        if button != Qt.MouseButton.LeftButton:
            return False

        key = self.active_key
        if self._is_complete(key):
            return False  # complete: drag handles, or Clear to redraw

        sx, sy = self.scene.scale_x, self.scene.scale_y
        self._points.setdefault(key, []).append([scene_pos.x() * sx, scene_pos.y() * sy])
        self._after_point_added(key)
        return True

    def handle_double_click(self, scene_pos: QPointF) -> bool:
        return self.finish_active()

    def finish_active(self) -> bool:
        key = self.active_key
        if key is None or STEP_BY_KEY[key].points is not None:
            return False
        if len(self._points.get(key, [])) < 3 or key in self._finished_open:
            return False
        self._finished_open.add(key)
        self._after_point_added(key, finishing=True)
        return True

    def undo_last_point(self, key: Optional[str] = None):
        """Removes the most recent point of `key` (defaults to the active
        step). Works even if the step was already complete — e.g. a wrong
        4th court corner, or a just-finished net — reverting it back to
        in-progress instead of forcing a full Clear."""
        key = key if key is not None else self.active_key
        if key is None:
            return
        pts = self._points.get(key)
        if not pts:
            return

        pts.pop()
        self._finished_open.discard(key)  # net re-opens for editing if it was finished
        if not pts:
            self._points.pop(key, None)

        self._redraw(key)
        self._mark_dirty()

    def _after_point_added(self, key, finishing=False):
        completed = self._is_complete(key)
        if completed and key == "court":
            self._points[key] = order_polygon_clockwise(self._points[key])
        self._redraw(key)
        self._mark_dirty()
        if completed and self.on_step_completed:
            self.on_step_completed(key)

    # ---------------- live preview line ----------------

    def _clear_guide(self):
        guide = getattr(self, "_guide", None)
        if guide is not None:
            self._safe_remove(guide)
            self._guide = None

    # ---------------- drawing ----------------

    def _to_display(self, pts) -> List[QPointF]:
        sx, sy = self.scene.scale_x or 1.0, self.scene.scale_y or 1.0
        return [QPointF(x / sx, y / sy) for x, y in pts]

    def _safe_remove(self, item):
        try:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
        except RuntimeError:
            pass  # scene.clear() already deleted the C++ object

    def _remove_items(self, key):
        item = self._shape_items.pop(key, None)
        if item is not None:
            self._safe_remove(item)
        for h in self._handles.pop(key, []):
            self._safe_remove(h)
        for t in self._labels.pop(key, []):
            self._safe_remove(t)

    def _drop_all_items(self):
        for key in list(self._shape_items) + list(self._handles) + list(self._labels):
            self._remove_items(key)
        self._shape_items.clear()
        self._handles.clear()
        self._labels.clear()

    def detach_items(self):
        """Forget item references WITHOUT touching the scene. Call right
        before scene.clear(), which deletes the C++ objects itself."""
        self._shape_items.clear()
        self._handles.clear()
        self._labels.clear()
        self._guide = None

    def rebuild_items(self):
        """Remove whatever exists, then redraw from stored points."""
        self._clear_guide()
        self._drop_all_items()
        if not self._visible:
            return
        for key in list(self._points):
            self._redraw(key)

    def _make_pen(self, color):
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        return pen

    def _make_label_item(self, text, color):
        item = QGraphicsSimpleTextItem(text)
        item.setBrush(QBrush(QColor(color)))
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        item.setFont(font)
        item.setZValue(1001)
        # Keeps label text a fixed screen size regardless of view zoom —
        # a name like "Down-Right Corner" stays legible even zoomed out.
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        return item

    def _redraw(self, key):
        self._clear_guide()
        self._remove_items(key)
        pts = self._points.get(key)
        if not pts or not self._visible:
            return

        step = STEP_BY_KEY[key]
        display = self._to_display(pts)
        pen = self._make_pen(step.color)

        shape = None
        if step.kind == "line" and len(display) >= 2:
            shape = QGraphicsLineItem(display[0].x(), display[0].y(),
                                      display[1].x(), display[1].y())
        elif step.kind == "polygon" and len(display) >= 2:
            shape = QGraphicsPolygonItem(QPolygonF(display))
            fill = QColor(step.color)
            fill.setAlpha(40)
            shape.setBrush(QBrush(fill))
        if shape is not None:
            shape.setPen(pen)
            shape.setZValue(900)
            self.scene.addItem(shape)
            self._shape_items[key] = shape

        handles = []
        for i, p in enumerate(display):
            h = _Handle(self, key, i, step.color)
            h.setPos(p)
            self.scene.addItem(h)
            h._ready = True
            handles.append(h)
        self._handles[key] = handles

        self._labels[key] = self._build_labels(key, pts, display, step.color)

    def _build_labels(self, key, pts, display, color) -> List[QGraphicsSimpleTextItem]:
        texts = compute_point_labels(key, pts)
        items = []
        for text, p in zip(texts, display):
            if not text:
                continue
            item = self._make_label_item(text, color)
            item.setPos(p + LABEL_OFFSET)
            self.scene.addItem(item)
            items.append(item)
        return items

    def _refresh_labels(self, key):
        """Cheap in-place label update during a drag — repositions/retexts
        existing text items without touching handles or the shape item.
        Falls back to a full rebuild if the number of VISIBLE labels
        changes (e.g. the net just gained its 2nd point)."""
        pts = self._points.get(key)
        if not pts:
            return
        step = STEP_BY_KEY[key]
        display = self._to_display(pts)
        texts = compute_point_labels(key, pts)

        visible_texts = [t for t in texts if t]
        existing = self._labels.get(key, [])
        if len(visible_texts) != len(existing):
            for t in existing:
                self._safe_remove(t)
            self._labels[key] = self._build_labels(key, pts, display, step.color)
            return

        i = 0
        for text, p in zip(texts, display):
            if not text:
                continue
            item = existing[i]
            item.setText(text)
            item.setPos(p + LABEL_OFFSET)
            i += 1

    def _handle_moved(self, key, index, pos: QPointF):
        pts = self._points.get(key)
        if not pts or index >= len(pts):
            return
        sx, sy = self.scene.scale_x, self.scene.scale_y
        pts[index] = [pos.x() * sx, pos.y() * sy]

        shape = self._shape_items.get(key)
        if shape is not None:
            display = self._to_display(pts)
            if isinstance(shape, QGraphicsLineItem):
                shape.setLine(display[0].x(), display[0].y(), display[1].x(), display[1].y())
            else:
                shape.setPolygon(QPolygonF(display))

        self._refresh_labels(key)
        self._mark_dirty()

    def update_draft_preview(self, scene_pos: QPointF):
        key = self.active_key
        pts = self._points.get(key) if key else None
        if not self._visible or not pts or self._is_complete(key):
            self._clear_guide()
            return
        last = self._to_display([pts[-1]])[0]
        if self._guide is None:
            pen = QPen(QColor(STEP_BY_KEY[key].color), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._guide = self.scene.addLine(last.x(), last.y(),
                                             scene_pos.x(), scene_pos.y(), pen)
            self._guide.setZValue(950)
            self._guide.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        else:
            self._guide.setLine(last.x(), last.y(), scene_pos.x(), scene_pos.y())
