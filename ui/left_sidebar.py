"""
Layer Sidebar Module for VB Annotator

This module provides the sidebar user interface for the VB Annotator application,
allowing users to manage layers, labels, annotation tools, and AI-assisted features.
The LayerSidebar widget serves as the main control panel for annotation operations.

Key Features:
- Layer management with visibility toggling
- Label selection for active layers
- Tool selection (rectangle, polygon)
- AI-assisted detection tools
- Dynamic UI updates based on layer selection
"""

from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QToolButton
)

from vb_gui.vb_annotator.resources.icons import rectangle_icon, polygon_icon


class LeftSideBar(QWidget):
    """
    Main sidebar widget for annotation controls.

    This widget provides the complete sidebar interface including layer management,
    label selection, tool selection, and AI assistance buttons. It maintains the
    current state of layers, labels, and tools, and emits signals when changes occur.

    Signals:
        layerChanged: Emitted when the active layer changes (str)
        labelChanged: Emitted when the active label changes (str)
        toolChanged: Emitted when the annotation tool changes (str)
        visibilityChanged: Emitted when a layer's visibility is toggled (str, bool)
    """

    layerChanged = pyqtSignal(str)
    labelChanged = pyqtSignal(str)
    toolChanged = pyqtSignal(str)
    visibilityChanged = pyqtSignal(str, bool)

    def __init__(self, db, parent=None):
        """
        Initialize the LayerSidebar widget.

        Args:
            db: Database connection object containing layer and label data
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        self.setFixedWidth(260)

        self.current_layer = "court"
        self.current_label = "net"
        self.current_tool = "rectangle"

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
        self.set_layer("court")
        self.set_tool("rectangle")

    def _build_ui(self):
        """
        Build the complete user interface for the sidebar.

        This method creates all UI components including:
        - Title header
        - Layer list with visibility controls
        - Label buttons for the active layer
        - Tool selection buttons
        - AI assistance buttons

        All styling is applied through the stylesheet defined in this method.
        """

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        title = QLabel("Annotation")
        title.setObjectName("title")
        layout.addWidget(title)

        layout.addWidget(self.separator())
        layout.addWidget(self.section("Layers"))

        for layer in ["court", "players", "ball", "actions"]:
            row = LayerRow(layer)
            row.clicked.connect(self.set_layer)
            row.visibilityChanged.connect(self.visibilityChanged.emit)

            self.layer_rows[layer] = row
            layout.addWidget(row)

        layout.addWidget(self.separator())
        layout.addWidget(self.section("Labels"))

        self.labels_container = QWidget()
        self.labels_layout = QVBoxLayout(self.labels_container)
        self.labels_layout.setContentsMargins(5, 5, 5, 5)
        self.labels_layout.setSpacing(5)

        layout.addWidget(self.labels_container)

        layout.addWidget(self.separator())

        layout.addWidget(self.section("Tools"))

        tools = QHBoxLayout()
        tools.setSpacing(8)

        icon_size = 30
        btn_size = 40
        self.rect_btn = QPushButton()
        self.rect_btn.setIcon(QIcon("./resources/icons/tools/rectangle.png"))
        self.rect_btn.setContentsMargins(0, 0, 0, 0)
        self.rect_btn.setFixedSize(btn_size, btn_size)
        self.rect_btn.setIconSize(QSize(icon_size, icon_size))
        self.rect_btn.setFont(QFont("Arial", 14))
        self.rect_btn.setToolTip("Rectangle Tool")
        self.rect_btn.clicked.connect(lambda: self.set_tool("rectangle"))

        self.poly_btn = QPushButton()
        self.poly_btn.setIcon(QIcon("./resources/icons/tools/pentagon.png"))
        self.poly_btn.setFixedSize(btn_size, btn_size)
        self.poly_btn.setIconSize(QSize(icon_size, icon_size))
        self.poly_btn.setFont(QFont("Arial", 14))
        self.poly_btn.setToolTip("Polygon Tool")
        self.poly_btn.clicked.connect(lambda: self.set_tool("polygon"))

        self.none_btn = QPushButton()
        self.none_btn.setIcon(QIcon("./resources/icons/tools/cursor.png"))
        self.none_btn.setFixedSize(btn_size, btn_size)
        self.none_btn.setIconSize(QSize(icon_size, icon_size))
        self.none_btn.setFont(QFont("Arial", 14))
        self.none_btn.setToolTip("Selection Tool (Esc)")
        self.none_btn.clicked.connect(lambda: self.set_tool("none"))


        tools.addWidget(self.rect_btn)
        tools.addWidget(self.poly_btn)
        tools.addWidget(self.none_btn)
        tools.addStretch()
        layout.addLayout(tools)
        layout.addWidget(self.separator())

        layout.addStretch()

    @staticmethod
    def separator():
        """
        Create a horizontal separator line.

        Returns:
            QFrame: A horizontal line frame for visual separation
        """
        line = QFrame()
        line.setObjectName("line")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    @staticmethod
    def section(text):
        """
        Create a section header label.

        Args:
            text (str): The section title text

        Returns:
            QLabel: A styled label for section headers
        """
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def set_layer(self, layer):
        """
        Set the active layer and update the UI accordingly.

        Args:
            layer (str): Name of the layer to activate
        """
        self.current_layer = layer
        self.layerChanged.emit(layer)

        for name, row in self.layer_rows.items():
            row.set_active(name == layer)
            row.style().unpolish(row)
            row.style().polish(row)

        self.rebuild_labels()

    def rebuild_labels(self):
        """
        Rebuild the label buttons for the current active layer.

        This method clears existing label buttons and creates new ones
        based on the labels available for the current layer.
        """
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
        """
        Set the active label and update the UI accordingly.

        Args:
            label (str): Name of the label to activate
        """
        self.current_label = label

        for name, btn in self.label_buttons.items():
            btn.setObjectName("activeLabel" if name == label else "labelButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.labelChanged.emit(label)

    def set_tool(self, tool):
        """User-initiated tool selection (from clicking a tool button). Emits toolChanged."""
        self._apply_tool_visuals(tool)
        self.toolChanged.emit(tool)

        for btn in [self.rect_btn, self.poly_btn, self.none_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.toolChanged.emit(tool)

    def clear_tool_selection(self):
        """
        Visually deselect both tool buttons (neutral cursor mode).
        Does not emit toolChanged — this is meant to be called in *response*
        to a mode change (e.g. Escape), not to trigger one.
        """
        self._apply_tool_visuals("none")

    def sync_tool_visuals(self, tool):
        """
        Reflect the active tool in the UI without emitting toolChanged.
        Used when MainWindow is the source of truth (e.g. syncing after the
        scene's tool mode changed) and calling set_tool would loop back here.
        """
        self._apply_tool_visuals(tool)

    def _apply_tool_visuals(self, tool):
        self.current_tool = tool

        self.rect_btn.setObjectName("toolActive" if tool == "rectangle" else "tool")
        self.poly_btn.setObjectName("toolActive" if tool == "polygon" else "tool")
        self.none_btn.setObjectName("toolActive" if tool == "none" else "tool")

        for btn in [self.rect_btn, self.poly_btn, self.none_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)


class LayerRow(QWidget):
    """
    Individual layer row widget for the sidebar.

    This widget represents a single layer in the layer list, providing
    click functionality for layer activation and visibility toggling.

    Signals:
        clicked: Emitted when the layer name is clicked (str)
        visibilityChanged: Emitted when visibility is toggled (str, bool)
    """

    clicked = pyqtSignal(str)
    visibilityChanged = pyqtSignal(str, bool)

    # lockChanged = pyqtSignal(str, bool)

    def __init__(self, layer_name):
        """
        Initialize a LayerRow widget.

        Args:
            layer_name (str): Name of the layer this row represents
        """
        super().__init__()

        self.layer_name = layer_name
        self.visible = True
        # self.locked = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self.name_btn = QPushButton(layer_name)
        self.name_btn.setFlat(True)
        self.name_btn.clicked.connect(
            lambda: self.clicked.emit(layer_name)
        )

        self.eye_btn = QToolButton()
        self.eye_btn.setText("👁")
        self.eye_btn.clicked.connect(self.toggle_visibility)

        layout.addWidget(self.name_btn, 1)
        layout.addWidget(self.eye_btn)
        # layout.addWidget(self.lock_btn)

        self.set_active(False)

    def set_active(self, active):
        """
        Set the visual state of the row to active or inactive.

        Args:
            active (bool): True to highlight as active, False otherwise
        """
        if active:
            self.setStyleSheet(
                "background:#E95420; border-radius:8px;"
            )
        else:
            self.setStyleSheet(
                "background:transparent;"
            )

    def toggle_visibility(self):
        """
        Toggle the visibility state of the layer and update the UI.

        This method toggles the visible flag and updates the eye button
        icon to reflect the current visibility state.
        """
        self.visible = not self.visible
        self.eye_btn.setText(
            "👁" if self.visible else "🚫"
        )
        self.visibilityChanged.emit(
            self.layer_name,
            self.visible,
        )


class LabelRow(QPushButton):
    """
    Individual label button widget.

    This class represents a single label button in the label list,
    displaying the label name with a color indicator.

    Note: This class is currently not used in the main widget but
    is maintained for potential future use.
    """

    def __init__(self, name, color):
        """
        Initialize a LabelRow widget.

        Args:
            name (str): Name of the label
            color (str): Color code for the label indicator
        """
        super().__init__()
        self.label_name = name
        self.setText(f"●  {name}")
