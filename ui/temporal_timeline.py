"""
Temporal Timeline widget for video game-state annotation.

One row per label (service / in-play / no-play). Segments are drawn as
colored bars; the user can:
  - click/drag on the top ruler to seek (with a visible playhead handle)
  - drag an interval's body to move it
  - drag an interval's edge to resize it
  - select an interval and delete it via "Delete Selected"

Editing is BATCHED: dragging a box only mutates it locally and marks it
dirty (dashed yellow outline). Nothing is written to the DB until the user
clicks "Apply Changes" (or the app's main Save also flushes pending edits
— see MainWindow). "Cancel Changes" reverts every dirty box back to its
last-loaded position without touching the DB.

Creating *new* intervals is NOT done here — that workflow (pick label ->
Mark Start -> Mark End) lives in the left sidebar's Video Annotation tab,
since a range isn't "real" until both ends exist. This widget only
visualizes committed segments (plus a live pending-create rectangle) and
lets you edit/delete what's already been saved.
"""
import math

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QToolButton, QScrollArea, QSlider, QCheckBox)

from .theme.colors import Colors
from .theme.theme_manager import ThemeManager
from .utils import create_navigation_button

STATE_COLORS = {
    "service": "#FF7A29",
    "play": "#3DDC84",
    "no-play": "#555A66",
    "unknown": "#3A3D46",
}
LABEL_ORDER = ["service", "play", "no-play"]
LABEL_DISPLAY = {"service": "Service", "play": "In-Play", "no-play": "No-Play"}

EDGE_PX = 6
ROW_HEIGHT = 34
RULER_HEIGHT = 22  # top ruler: frame-number ticks
TIME_RULER_HEIGHT = 20  # bottom ruler: mm:ss ticks
BOTTOM_PADDING = 10  # breathing room below the time ruler
LABEL_COL_WIDTH = 74


class TimelineCanvas(QWidget):
    seekRequested = pyqtSignal(int)
    pendingEditsChanged = pyqtSignal(bool)  # True if any box has an uncommitted drag
    intervalSelected = pyqtSignal(object)  # GameStateSegment-like or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.segments = []
        self.max_frame = 0
        self.pixels_per_frame = 2.0
        self.current_frame = 0
        self.fps = 30.0
        self.pending_marker = None  # (frame, state) or None — live create-in-progress
        self.selected_segment_id = None

        self._clean_by_id = {}  # segment_id -> (start, end) as last loaded from DB
        self._pending_edits = {}  # segment_id -> (start, end) currently dirty

        self._drag_mode = None  # None | "seek" | "move" | "resize_start" | "resize_end"
        self._drag_segment = None
        self._drag_anchor_frame = 0
        self._drag_orig_start = 0
        self._drag_orig_end = 0

        total_h = RULER_HEIGHT + ROW_HEIGHT * len(LABEL_ORDER) + TIME_RULER_HEIGHT + BOTTOM_PADDING
        self.setMinimumHeight(total_h)
        self._recalc_width()
        ThemeManager.instance().themeChanged.connect(lambda _: self.update())

    # ---------------- Public API ----------------

    def set_segments(self, segments):
        """Called with fresh data from the DB (initial load, or after a
        successful Apply/delete). Resets the dirty baseline."""
        self.segments = list(segments or [])
        self._clean_by_id = {s.segment_id: (s.start_frame, s.end_frame) for s in self.segments}
        self._pending_edits = {}
        if self.selected_segment_id is not None:
            if not any(s.segment_id == self.selected_segment_id for s in self.segments):
                self.selected_segment_id = None
                self.intervalSelected.emit(None)
        self.pendingEditsChanged.emit(False)
        self.update()

    def discard_pending_edits(self):
        """Revert every dirty box back to its last-loaded position."""
        for seg in self.segments:
            baseline = self._clean_by_id.get(seg.segment_id)
            if baseline is not None:
                seg.start_frame, seg.end_frame = baseline
        self._pending_edits = {}
        self.pendingEditsChanged.emit(False)
        self.update()

    def get_pending_edits(self):
        """dict[segment_id] -> (start_frame, end_frame) for every box whose
        range currently differs from what was last loaded."""
        return dict(self._pending_edits)

    def set_max_frame(self, max_frame):
        self.max_frame = max(0, max_frame)
        self._recalc_width()
        self.update()

    def set_pixels_per_frame(self, ppf):
        self.pixels_per_frame = max(0.1, ppf)
        self._recalc_width()
        self.update()

    def set_current_frame(self, frame):
        self.current_frame = frame
        self.update()

    def set_fps(self, fps):
        self.fps = fps if fps and fps > 0 else 30.0
        self.update()

    def set_pending_marker(self, frame, state):
        self.pending_marker = (frame, state) if frame is not None else None
        self.update()

    def _recalc_width(self):
        width = LABEL_COL_WIDTH + int(self.max_frame * self.pixels_per_frame) + 40
        self.setMinimumWidth(max(width, 400))

    # ---------------- Geometry helpers ----------------

    def _frame_to_x(self, frame):
        return LABEL_COL_WIDTH + frame * self.pixels_per_frame

    def _x_to_frame(self, x):
        """
        Inverse of _frame_to_x. floor() is the mathematically correct
        inverse for a left-edge-anchored, half-open pixel interval, but
        pixels_per_frame (zoom_slider_value / 10.0) isn't always exactly
        representable in binary floating point — e.g. 1.3 — so
        frame_to_x(5) can compute to 4.999999999999999 instead of 5.0,
        and a bare floor() would then round DOWN to frame 4. The epsilon
        absorbs that representation error without meaningfully affecting
        real fractional positions (it's ~1000x smaller than one pixel).
        """
        raw = (x - LABEL_COL_WIDTH) / self.pixels_per_frame
        frame = math.floor(raw + 1e-6)
        return max(0, min(self.max_frame, frame))

    def _row_rect(self, index):
        top = RULER_HEIGHT + index * ROW_HEIGHT
        return QRectF(LABEL_COL_WIDTH, top, max(self.width() - LABEL_COL_WIDTH, 0), ROW_HEIGHT)

    def _segment_rect(self, seg):
        row = LABEL_ORDER.index(seg.state) if seg.state in LABEL_ORDER else len(LABEL_ORDER) - 1
        top = RULER_HEIGHT + row * ROW_HEIGHT + 4
        x1 = self._frame_to_x(seg.start_frame)
        x2 = self._frame_to_x(seg.end_frame + 1)
        return QRectF(x1, top, max(2.0, x2 - x1), ROW_HEIGHT - 8)

    def _pending_rect(self):
        """Live rectangle for an in-progress create: pending start frame to
        the current playhead frame, drawn in the pending state's row."""
        if self.pending_marker is None:
            return None

        p_frame, p_state = self.pending_marker
        start_f, end_f = sorted((p_frame, self.current_frame))

        row = LABEL_ORDER.index(p_state) if p_state in LABEL_ORDER else len(LABEL_ORDER) - 1
        top = RULER_HEIGHT + row * ROW_HEIGHT + 4
        x1 = self._frame_to_x(start_f)
        x2 = self._frame_to_x(end_f + 1)
        return QRectF(x1, top, max(2.0, x2 - x1), ROW_HEIGHT - 8), p_state

    def _nice_tick_step(self):
        target_px = 80
        raw = target_px / max(self.pixels_per_frame, 0.01)
        for step in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 3000):
            if step >= raw:
                return step
        return 3000

    def _format_time(self, frame):
        fps = self.fps if self.fps > 0 else 30.0
        total_seconds = int(frame / fps)

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # ---------------- Painting ----------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(Colors.BG_APP))

        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        # ---- Label rows ----
        for i, label in enumerate(LABEL_ORDER):
            row_rect = self._row_rect(i)
            bg = QColor(Colors.BG_SURFACE) if i % 2 == 0 else QColor(Colors.BG_APP)
            painter.fillRect(QRectF(0, row_rect.top(), self.width(), ROW_HEIGHT), bg)
            painter.setPen(QColor(Colors.TEXT_PRIMARY))
            painter.drawText(
                QRectF(8, row_rect.top(), LABEL_COL_WIDTH - 12, ROW_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                LABEL_DISPLAY[label],
            )

        # ---- Top ruler: frame numbers ----
        painter.setPen(QColor(Colors.TEXT_MUTED))
        step = self._nice_tick_step()
        f = 0
        while f <= self.max_frame:
            x = self._frame_to_x(f)
            painter.drawLine(QPointF(x, RULER_HEIGHT - 6), QPointF(x, RULER_HEIGHT))
            painter.drawText(QRectF(x - 30, 0, 60, RULER_HEIGHT - 6),
                             Qt.AlignmentFlag.AlignCenter, str(f))
            f += step

        # ---- Segments ----
        for seg in self.segments:
            rect = self._segment_rect(seg)
            color = QColor(STATE_COLORS.get(seg.state, STATE_COLORS["unknown"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 4, 4)

            if getattr(seg, "source", "model") == "manual":
                painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, 4, 4)

            if seg.segment_id in self._pending_edits:
                # Dirty — dragged but not yet applied.
                painter.setPen(QPen(QColor("#FFD814"), 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 5, 5)

            if getattr(seg, "segment_id", None) == self.selected_segment_id:
                painter.setPen(QPen(QColor("#00C8FF"), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect.adjusted(-4, -4, 4, 4), 6, 6)

        # ---- Live pending-create rectangle ----
        pending = self._pending_rect()
        if pending is not None:
            rect, p_state = pending
            color = QColor(STATE_COLORS.get(p_state, "#FFFFFF"))

            fill = QColor(color)
            fill.setAlpha(90)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 4, 4)

            pen = QPen(color, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 4, 4)

            p_frame, _ = self.pending_marker
            start_x = self._frame_to_x(p_frame)
            painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine))
            painter.drawLine(QPointF(start_x, RULER_HEIGHT), QPointF(start_x, self.height()))

        # ---- Bottom ruler: time ----
        rows_bottom = RULER_HEIGHT + ROW_HEIGHT * len(LABEL_ORDER)
        painter.fillRect(QRectF(0, rows_bottom, self.width(), TIME_RULER_HEIGHT), QColor(Colors.BG_PANEL_ALT))
        painter.setPen(QColor("#5A5F6B"))
        f = 0
        while f <= self.max_frame:
            x = self._frame_to_x(f)
            painter.drawLine(QPointF(x, rows_bottom), QPointF(x, rows_bottom + 5))
            painter.drawText(
                QRectF(x - 30, rows_bottom + 4, 60, TIME_RULER_HEIGHT - 4),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self._format_time(f),
            )
            f += step

        # ---- Playhead (drawn last, on top of everything) ----
        x = self._frame_to_x(self.current_frame)
        painter.setPen(QPen(QColor(Colors.ACCENT), 2))
        painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))

        # Playhead handle — small triangle at the very top, so the seek
        # line reads as grabbable (matches the seek-bar handle look).
        handle_half = 6
        handle_h = 8
        path = QPainterPath()
        path.moveTo(x - handle_half, 0)
        path.lineTo(x + handle_half, 0)
        path.lineTo(x, handle_h)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(Colors.ACCENT))
        painter.drawPath(path)

    # ---------------- Mouse interaction ----------------

    def _segment_at(self, pos):
        for seg in self.segments:
            rect = self._segment_rect(seg)
            if rect.adjusted(-EDGE_PX, 0, EDGE_PX, 0).contains(pos):
                return seg
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()

        # Clicking/dragging the top ruler always seeks — this is the
        # playhead's "handle" area.
        if pos.y() < RULER_HEIGHT:
            self._drag_mode = "seek"
            frame = self._x_to_frame(pos.x())
            self.current_frame = frame
            self.seekRequested.emit(frame)
            self.update()
            return

        seg = self._segment_at(pos)

        if seg is None:
            self.selected_segment_id = None
            self.intervalSelected.emit(None)
            self.seekRequested.emit(self._x_to_frame(pos.x()))
            self.update()
            return

        self.selected_segment_id = seg.segment_id
        self.intervalSelected.emit(seg)

        rect = self._segment_rect(seg)
        self._drag_segment = seg
        self._drag_orig_start = seg.start_frame
        self._drag_orig_end = seg.end_frame
        self._drag_anchor_frame = self._x_to_frame(pos.x())

        if abs(pos.x() - rect.left()) <= EDGE_PX:
            self._drag_mode = "resize_start"
        elif abs(pos.x() - rect.right()) <= EDGE_PX:
            self._drag_mode = "resize_end"
        else:
            self._drag_mode = "move"

        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()

        if self._drag_mode == "seek":
            frame = self._x_to_frame(pos.x())
            if frame != self.current_frame:
                self.current_frame = frame
                self.seekRequested.emit(frame)
                self.update()
            return

        if self._drag_mode is None:
            seg = self._segment_at(pos)
            if pos.y() < RULER_HEIGHT:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif seg is not None:
                rect = self._segment_rect(seg)
                if abs(pos.x() - rect.left()) <= EDGE_PX or abs(pos.x() - rect.right()) <= EDGE_PX:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
                else:
                    self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        frame = self._x_to_frame(pos.x())
        seg = self._drag_segment

        if self._drag_mode == "resize_start":
            seg.start_frame = min(frame, self._drag_orig_end)
        elif self._drag_mode == "resize_end":
            seg.end_frame = max(frame, self._drag_orig_start)
        elif self._drag_mode == "move":
            delta = frame - self._drag_anchor_frame
            length = self._drag_orig_end - self._drag_orig_start
            new_start = max(0, min(self.max_frame - length, self._drag_orig_start + delta))
            seg.start_frame = new_start
            seg.end_frame = new_start + length

        self.update()

    def mouseReleaseEvent(self, event):
        if self._drag_mode in ("move", "resize_start", "resize_end") and self._drag_segment is not None:
            seg = self._drag_segment
            baseline = self._clean_by_id.get(seg.segment_id)
            current = (seg.start_frame, seg.end_frame)

            if baseline is not None and current != baseline:
                self._pending_edits[seg.segment_id] = current
            elif seg.segment_id in self._pending_edits and current == baseline:
                del self._pending_edits[seg.segment_id]

            self.pendingEditsChanged.emit(bool(self._pending_edits))

        self._drag_mode = None
        self._drag_segment = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ---------------- Boundary / state navigation ----------------

    def _sorted_segments(self):
        return sorted(self.segments, key=lambda s: s.start_frame)

    def _segment_at_frame(self, frame):
        for seg in self.segments:
            if seg.start_frame <= frame <= seg.end_frame:
                return seg
        return None

    def _next_segment_after(self, frame):
        """Earliest segment that starts strictly after `frame`, or None."""
        candidates = [s for s in self._sorted_segments() if s.start_frame > frame]
        return min(candidates, key=lambda s: s.start_frame) if candidates else None

    def _prev_segment_before(self, frame):
        """Latest segment that ends strictly before `frame`, or None."""
        candidates = [s for s in self._sorted_segments() if s.end_frame < frame]
        return max(candidates, key=lambda s: s.end_frame) if candidates else None

    def _seek(self, frame):
        frame = max(0, min(self.max_frame, frame))
        if frame != self.current_frame:
            self.current_frame = frame
            self.seekRequested.emit(frame)
            self.update()

    def jump_to_next_boundary(self):
        """
        If the playhead sits inside a tagged segment, jump to that
        segment's end frame. If it's already there (or sitting in an
        untagged gap), jump to the start of whatever segment comes next
        — so repeated clicks always keep moving forward through the
        timeline instead of getting stuck.
        """
        frame = self.current_frame
        seg = self._segment_at_frame(frame)

        if seg is not None and seg.end_frame > frame:
            self._seek(seg.end_frame)
            return

        nxt = self._next_segment_after(frame)
        if nxt is not None:
            self._seek(nxt.start_frame)

    def jump_to_previous_boundary(self):
        """Mirror of jump_to_next_boundary, moving backward."""
        frame = self.current_frame
        seg = self._segment_at_frame(frame)

        if seg is not None and seg.start_frame < frame:
            self._seek(seg.start_frame)
            return

        prev = self._prev_segment_before(frame)
        if prev is not None:
            self._seek(prev.end_frame)

    def jump_to_next_state(self, state: str):
        """Jump to the start of the nearest upcoming segment tagged
        `state` (e.g. 'play' for In-Play)."""
        frame = self.current_frame
        candidates = [
            s for s in self._sorted_segments()
            if s.state == state and s.start_frame > frame
        ]
        if candidates:
            self._seek(min(candidates, key=lambda s: s.start_frame).start_frame)

    def jump_to_previous_state(self, state: str):
        """Jump to the start of the nearest preceding segment tagged
        `state`."""
        frame = self.current_frame
        candidates = [
            s for s in self._sorted_segments()
            if s.state == state and s.end_frame < frame
        ]
        if candidates:
            self._seek(max(candidates, key=lambda s: s.end_frame).start_frame)


class TemporalTimelinePanel(QWidget):
    """Collapsible container: header (toggle + zoom + apply/cancel/delete) + scrollable canvas."""

    seekRequested = pyqtSignal(int)
    applyChangesRequested = pyqtSignal(dict)  # segment_id -> (start, end)
    intervalDeleteRequested = pyqtSignal(int)  # segment_id
    clearAllRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_segment = None
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("timelineHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)

        # QToolButton + arrow-type icon instead of a unicode glyph, so the
        # collapse indicator always renders regardless of font coverage.
        self.toggle_btn = QToolButton()
        self.toggle_btn.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle_btn.setText(" Temporal Timeline")
        self.toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_btn.setAutoRaise(True)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle_collapsed)
        h_layout.addWidget(self.toggle_btn)
        h_layout.addStretch()

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 60)  # pixels-per-frame * 10
        self.zoom_slider.setValue(20)
        self.zoom_slider.setFixedWidth(120)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)

        self.canvas = TimelineCanvas()
        self.canvas.set_pixels_per_frame(self.zoom_slider.value() / 10.0)
        self.canvas.seekRequested.connect(self.seekRequested.emit)
        self.canvas.intervalSelected.connect(self._on_interval_selected)
        self.canvas.pendingEditsChanged.connect(self._on_pending_changed)

        # ---- NEW: boundary / in-play navigation ----
        self.prev_inplay_btn = create_navigation_button(
            tooltip="Previous In-Play segment",
            icon_path="./resources/icons/bottom_toolbar/prevprev.png",
            callback=lambda: self.canvas.jump_to_previous_state("play"),
            object_name="navigationButton",
            icon_size=18,
        )
        self.prev_boundary_btn = create_navigation_button(
            tooltip="Jump to start of current segment",
            icon_path="./resources/icons/bottom_toolbar/prev.png",
            callback=self.canvas.jump_to_previous_boundary,
            object_name="navigationButton",
            icon_size=18,
        )
        self.next_boundary_btn = create_navigation_button(
            tooltip="Jump to end of current segment",
            icon_path="./resources/icons/bottom_toolbar/next.png",
            callback=self.canvas.jump_to_next_boundary,
            object_name="navigationButton",
            icon_size=18,
        )
        self.next_inplay_btn = create_navigation_button(
            tooltip="Next In-Play segment",
            icon_path="./resources/icons/bottom_toolbar/nextnext.png",
            callback=lambda: self.canvas.jump_to_next_state("play"),
            object_name="navigationButton",
            icon_size=18,
        )

        h_layout.addWidget(self.prev_inplay_btn)
        h_layout.addWidget(self.prev_boundary_btn)
        h_layout.addWidget(self.next_boundary_btn)
        h_layout.addWidget(self.next_inplay_btn)

        h_layout.addWidget(QLabel("Zoom"))
        h_layout.addWidget(self.zoom_slider)

        self.follow_checkbox = QCheckBox("Follow Playhead")
        self.follow_checkbox.setChecked(True)
        h_layout.addWidget(self.follow_checkbox)

        self.apply_btn = QPushButton("Apply Changes")

        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.setVisible(False)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        h_layout.addWidget(self.apply_btn)

        self.discard_btn = QPushButton("Cancel Changes")
        self.discard_btn.setVisible(False)
        self.discard_btn.clicked.connect(self._on_discard_clicked)
        h_layout.addWidget(self.discard_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        h_layout.addWidget(self.delete_btn)

        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setObjectName("dangerButton")
        self.clear_all_btn.setEnabled(False)
        self.clear_all_btn.clicked.connect(self.clearAllRequested.emit)
        h_layout.addWidget(self.clear_all_btn)

        outer.addWidget(header)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        total_h = RULER_HEIGHT + ROW_HEIGHT * len(LABEL_ORDER) + TIME_RULER_HEIGHT + BOTTOM_PADDING
        self.scroll_area.setFixedHeight(total_h + 4)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_area.setWidget(self.canvas)
        content_layout.addWidget(self.scroll_area)

        outer.addWidget(self.content)
        self._collapsed = False

    def _toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.content.setVisible(not self._collapsed)
        self.toggle_btn.setArrowType(
            Qt.ArrowType.RightArrow if self._collapsed else Qt.ArrowType.DownArrow
        )

    def _on_zoom_changed(self, value):
        self.canvas.set_pixels_per_frame(value / 10.0)

    def _on_interval_selected(self, segment):
        self._selected_segment = segment
        self.delete_btn.setEnabled(segment is not None)

    def _on_pending_changed(self, has_pending):
        self.apply_btn.setVisible(has_pending)
        self.discard_btn.setVisible(has_pending)

    def _on_apply_clicked(self):
        edits = self.canvas.get_pending_edits()
        if edits:
            self.applyChangesRequested.emit(edits)

    def _on_discard_clicked(self):
        self.canvas.discard_pending_edits()

    def _on_delete_clicked(self):
        if self._selected_segment is not None:
            self.intervalDeleteRequested.emit(self._selected_segment.segment_id)
            self._selected_segment = None
            self.delete_btn.setEnabled(False)

    def _autoscroll_to_playhead(self, frame):
        """
        Keep the playhead visible the way a video editor's "follow
        playhead" does: the view holds still while the playhead moves
        within the current page, then jumps exactly one page-width
        forward or back the instant the playhead crosses the visible
        edge — rather than smoothly scrolling every frame, which would
        make the timeline feel like it's crawling under the cursor.
        """
        if not self.follow_checkbox.isChecked():
            return

        viewport_width = self.scroll_area.viewport().width()
        if viewport_width <= 0:
            return

        x = self.canvas._frame_to_x(frame)
        scrollbar = self.scroll_area.horizontalScrollBar()
        visible_start = scrollbar.value()
        visible_end = visible_start + viewport_width

        if x < visible_start or x > visible_end:
            page_index = int(x // viewport_width)
            target = max(0, min(page_index * viewport_width, scrollbar.maximum()))
            scrollbar.setValue(target)

    # ---------------- Public API ----------------

    def set_segments(self, segments):
        self.canvas.set_segments(segments)
        self.clear_all_btn.setEnabled(bool(segments))

    def set_max_frame(self, max_frame):
        self.canvas.set_max_frame(max_frame)

    def set_current_frame(self, frame):
        self.canvas.set_current_frame(frame)
        self._autoscroll_to_playhead(frame)

    def set_fps(self, fps):
        self.canvas.set_fps(fps)

    def set_pending_marker(self, frame, state):
        self.canvas.set_pending_marker(frame, state)

    def get_pending_edits(self):
        return self.canvas.get_pending_edits()
