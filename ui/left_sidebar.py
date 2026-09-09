"""
Left Sidebar Module for VB Annotator

Two tabs:
  - "Frame Annotations": the existing per-frame layer/label/tool controls
    (YOLO-style rectangle/polygon annotation) — unchanged behavior.
  - "Video Annotations": the manual game-state tagging workflow (pick a
    label, Mark Start, Mark End). Editing/deleting already-saved segments
    happens on the Temporal Timeline panel, not here.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFrame, QTabWidget)
from vb_gui.vb_annotator.ui.utils import create_navigation_button
from vb_gui.vb_annotator.ui.temporal_timeline import STATE_COLORS


def _separator():
    line = QFrame()
    line.setObjectName("line")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


def _section(text):
    label = QLabel(text)
    label.setObjectName("section")
    return label


class LeftSideBar(QWidget):
    """
    Top-level left sidebar: hosts the Frame/Video tab widget and re-emits
    the Frame tab's signals under the same names MainWindow already
    connects to, plus new signals for the Video tab's create-flow.
    """

    # Frame Annotation tab (unchanged public surface)
    layerChanged = pyqtSignal(str)
    labelChanged = pyqtSignal(str)
    toolChanged = pyqtSignal(str)

    # Video Annotation tab (new)
    videoLabelChanged = pyqtSignal(str)
    videoMarkStartRequested = pyqtSignal(str)
    videoMarkEndRequested = pyqtSignal()
    videoCancelRequested = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setFixedWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.frame_tab = FrameAnnotationTab(db)
        self.frame_tab.layerChanged.connect(self.layerChanged.emit)
        self.frame_tab.labelChanged.connect(self.labelChanged.emit)
        self.frame_tab.toolChanged.connect(self.toolChanged.emit)
        self.tabs.addTab(self.frame_tab, "Frame Annotations")

        self.video_tab = VideoAnnotationTab()
        self.video_tab.labelChanged.connect(self.videoLabelChanged.emit)
        self.video_tab.markStartRequested.connect(self.videoMarkStartRequested.emit)
        self.video_tab.markEndRequested.connect(self.videoMarkEndRequested.emit)
        self.video_tab.cancelRequested.connect(self.videoCancelRequested.emit)
        self.tabs.addTab(self.video_tab, "Video Annotations")

    # ---------------------------------------------------------
    # Delegation — keeps MainWindow's existing calls (set_layer,
    # set_tool, sync_tool_visuals, clear_tool_selection) working
    # unchanged against the Frame tab.
    # ---------------------------------------------------------

    def set_layer(self, layer):
        self.frame_tab.set_layer(layer)

    def set_tool(self, tool):
        self.frame_tab.set_tool(tool)

    def sync_tool_visuals(self, tool):
        self.frame_tab.sync_tool_visuals(tool)

    def clear_tool_selection(self):
        self.frame_tab.clear_tool_selection()

    # ---------------------------------------------------------
    # Video tab delegation
    # ---------------------------------------------------------

    def set_video_tag_pending(self, pending: bool, start_frame=None, state=None):
        self.video_tab.set_pending(pending, start_frame, state)

    def cycle_layer(self):
        self.frame_tab.cycle_layer()

    def cycle_frame_label(self):
        self.frame_tab.cycle_label()

    def cycle_video_label(self):
        self.video_tab.cycle_label()


class FrameAnnotationTab(QWidget):
    """
    Per-frame annotation controls: layers, labels, and drawing tools.
    This is the old LeftSideBar body, unchanged aside from the rename.
    """

    LAYER_ORDER = ["ball", "players", "actions", "court"]
    layerChanged = pyqtSignal(str)
    labelChanged = pyqtSignal(str)
    toolChanged = pyqtSignal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)

        self.current_layer = None
        self.current_label = None
        self.current_tool = None

        self.layer_rows = {}
        self.label_buttons = {}
        self.db = db
        layers = self.db.get_layers()
        self.setObjectName("leftSidebar")

        self.layer_labels = {
            layer.name: [
                (label.name, label.color)
                for label in layer.labels
            ]
            for layer in layers
        }

        self._build_ui()
        self.set_layer("ball")
        self.set_tool("none")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        title = QLabel("Annotation")
        title.setObjectName("title")
        layout.addWidget(title)

        layout.addWidget(_separator())
        layout.addWidget(_section("Layers"))

        for layer in ["ball", "players", "actions", "court"]:
            row = LayerRow(layer)
            row.clicked.connect(self.set_layer)
            self.layer_rows[layer] = row
            layout.addWidget(row)

        layout.addWidget(_separator())
        layout.addWidget(_section("Labels"))

        self.labels_container = QWidget()
        self.labels_layout = QVBoxLayout(self.labels_container)
        self.labels_layout.setContentsMargins(5, 5, 5, 5)
        self.labels_layout.setSpacing(5)
        layout.addWidget(self.labels_container)

        layout.addWidget(_separator())
        layout.addWidget(_section("Tools"))

        tools = QHBoxLayout()
        tools.setSpacing(8)
        icon_size = 28

        self.none_btn = create_navigation_button(
            tooltip="Selection tool (Esc)",
            icon_path="./resources/icons/tools/cursor.png",
            callback=lambda: self.set_tool("none"),
            object_name="tool",
            icon_size=icon_size - 5,
        )
        self.rect_btn = create_navigation_button(
            tooltip="Rectangle Tool (R)",
            icon_path="./resources/icons/tools/rectangle.png",
            callback=lambda: self.set_tool("rectangle"),
            object_name="tool",
            icon_size=icon_size,
        )
        self.poly_btn = create_navigation_button(
            tooltip="Polygon Tool (P)",
            icon_path="./resources/icons/tools/pentagon.png",
            callback=lambda: self.set_tool("polygon"),
            object_name="tool",
            icon_size=icon_size,
        )

        tools.addWidget(self.none_btn)
        tools.addWidget(self.rect_btn)
        tools.addWidget(self.poly_btn)
        tools.addStretch()
        layout.addLayout(tools)
        layout.addWidget(_separator())
        layout.addStretch()

    def set_layer(self, layer):
        self.current_layer = layer
        self.layerChanged.emit(layer)

        for name, row in self.layer_rows.items():
            row.set_active(name == layer)
            row.style().unpolish(row)
            row.style().polish(row)

        self.rebuild_labels()

    def rebuild_labels(self):
        while self.labels_layout.count():
            item = self.labels_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.label_buttons.clear()

        labels = self.layer_labels[self.current_layer]
        self.current_label = labels[0][0]

        for name, color in labels:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked=False, n=name: self.set_label(n))
            self.label_buttons[name] = btn
            self.labels_layout.addWidget(btn)

        self.set_label(self.current_label)

    def set_label(self, label):
        self.current_label = label
        for name, btn in self.label_buttons.items():
            btn.setObjectName("activeLabel" if name == label else "labelButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.labelChanged.emit(label)

    def set_tool(self, tool):
        """User-initiated tool selection. Emits toolChanged."""
        self._apply_tool_visuals(tool)
        self.toolChanged.emit(tool)
        for btn in [self.rect_btn, self.poly_btn, self.none_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def clear_tool_selection(self):
        self._apply_tool_visuals("none")

    def sync_tool_visuals(self, tool):
        self._apply_tool_visuals(tool)

    def _apply_tool_visuals(self, tool):
        self.current_tool = tool
        self.rect_btn.setObjectName("toolActive" if tool == "rectangle" else "tool")
        self.poly_btn.setObjectName("toolActive" if tool == "polygon" else "tool")
        self.none_btn.setObjectName("toolActive" if tool == "none" else "tool")

        for btn in [self.rect_btn, self.poly_btn, self.none_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def cycle_layer(self):
        idx = self.LAYER_ORDER.index(self.current_layer) if self.current_layer in self.LAYER_ORDER else -1
        next_layer = self.LAYER_ORDER[(idx + 1) % len(self.LAYER_ORDER)]
        self.set_layer(next_layer)

    def cycle_label(self):
        names = [name for name, _ in self.layer_labels[self.current_layer]]
        if not names:
            return
        idx = names.index(self.current_label) if self.current_label in names else -1
        next_name = names[(idx + 1) % len(names)]
        self.set_label(next_name)


class VideoLabelRow(QWidget):
    """
    Row for selecting a game-state label — styled like the Frame tab's
    LayerRow (click to activate, orange highlight when active), with a
    color swatch matching that label's color on the Temporal Timeline.
    """
    clicked = pyqtSignal(str)

    def __init__(self, key, display, color):
        super().__init__()
        self.key = key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        swatch = QLabel()
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(f"background:{color}; border-radius:3px;")
        layout.addWidget(swatch)

        self.name_btn = QPushButton(display)
        self.name_btn.setFlat(True)
        self.name_btn.clicked.connect(lambda: self.clicked.emit(key))
        layout.addWidget(self.name_btn, 1)

        self.set_active(False)

    def set_active(self, active):
        if active:
            self.setStyleSheet("background:#E95420; border-radius:8px;")
        else:
            self.setStyleSheet("background:transparent;")

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.name_btn.setEnabled(enabled)


class VideoAnnotationTab(QWidget):
    """
    Manual game-state tagging: pick a label, Mark Start, Mark End.
    Nothing is written to the DB until both ends are set. Editing an
    already-saved segment's range happens on the Temporal Timeline, not
    here — this tab only creates new ones.
    """

    labelChanged = pyqtSignal(str)
    markStartRequested = pyqtSignal(str)
    markEndRequested = pyqtSignal()
    cancelRequested = pyqtSignal()

    STATES = [("service", "Service"), ("play", "In-Play"), ("no-play", "No-Play")]
    STATE_ORDER = [key for key, _ in STATES]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending = False
        self.current_state = "service"
        self.label_rows = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        layout.addWidget(_section("Game State Label  (Alt+3 to cycle)"))

        for key, display in self.STATES:
            row = VideoLabelRow(key, display, STATE_COLORS.get(key, "#FFFFFF"))
            row.clicked.connect(self.set_label)
            self.label_rows[key] = row
            layout.addWidget(row)

        self.set_label(self.current_state)

        layout.addWidget(_separator())

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.action_button = QPushButton("Mark Start")
        self.action_button.setFixedHeight(32)
        self.action_button.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.action_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(28)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        layout.addWidget(self.cancel_button)

        layout.addWidget(_separator())

        hint = QLabel(
            "Pick a label, then Mark Start at the beginning of the segment "
            "and Mark End where it ends — nothing is saved until both ends "
            "are set. Already-saved tags can be dragged, resized, or "
            "deleted directly on the Temporal Timeline below the video."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9096A3; font-size: 11px;")
        layout.addWidget(hint)

        layout.addStretch()

    def set_label(self, key):
        self.current_state = key
        for name, row in self.label_rows.items():
            row.set_active(name == key)
        self.labelChanged.emit(key)

    def cycle_label(self):
        if self._pending:
            return  # don't allow switching label mid-tag
        idx = self.STATE_ORDER.index(self.current_state)
        next_state = self.STATE_ORDER[(idx + 1) % len(self.STATE_ORDER)]
        self.set_label(next_state)

    def _on_action_clicked(self):
        if self._pending:
            self.markEndRequested.emit()
        else:
            self.markStartRequested.emit(self.current_state)

    def set_pending(self, pending: bool, start_frame=None, state=None):
        self._pending = pending
        for row in self.label_rows.values():
            row.setEnabled(not pending)

        if pending:
            self.action_button.setText("Mark End")
            self.cancel_button.setVisible(True)
            self.status_label.setText(
                f"Marking '{state}' — start at frame {start_frame}. "
                f"Move to the end frame and click Mark End."
            )
        else:
            self.action_button.setText("Mark Start")
            self.cancel_button.setVisible(False)
            self.status_label.setText("")


class LayerRow(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, layer_name):
        super().__init__()
        self.layer_name = layer_name
        self.visible = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self.name_btn = QPushButton(layer_name)
        self.name_btn.setFlat(True)
        self.name_btn.clicked.connect(lambda: self.clicked.emit(layer_name))
        layout.addWidget(self.name_btn, 1)

        self.set_active(False)

    def set_active(self, active):
        if active:
            self.setStyleSheet("background:#E95420; border-radius:8px;")
        else:
            self.setStyleSheet("background:transparent;")


class LabelRow(QPushButton):
    def __init__(self, name, color):
        super().__init__()
        self.label_name = name
        self.setText(f"●  {name}")
