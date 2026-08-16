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
        self.setStyleSheet("""
            QWidget {
                background: #1E1F24;
                color: #E6E6E6;
                font-size: 13px;
            }

            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: #F1F3F5;
            }

            QLabel#section {
                font-size: 11px;
                font-weight: bold;
                color: #9AA0A6;
                margin-top: 10px;
                letter-spacing: 0.5px;
            }

            QFrame#line {
                background: #2A2D34;
                max-height: 1px;
                min-height: 1px;
            }

            /* ---------- Layer rows ---------- */

            QPushButton {
                background: transparent;
                border: none;
                padding: 8px 10px;
                text-align: left;
                border-radius: 8px;
                color: #E6E6E6;
            }

            QPushButton:hover {
                background: #323540;
                border: 1px solid #E95420;
            }

            QPushButton#activeLayer {
                background: #E95420;
                color: white;
                font-weight: 600;
            }

            QPushButton#labelButton {
                background: transparent;
                border: none;
                padding: 8px 10px;
                text-align: left;
                border-radius: 8px;
                color: #D8DADF;
            }

            QPushButton#labelButton:hover {
                background: #323540;
            }

            QPushButton#activeLabel {
                background: #2C313A;
                border: 1px solid #E95420;
                border-radius: 8px;
                color: white;
                font-weight: 600;
            }

            /* ---------- Tool buttons ---------- */

            QPushButton#tool {
                background: #2C313A;
                border: 1px solid #3A3F4B;
                border-radius: 10px;
                color: #E6E6E6;
                margin=0px;
                min-width: 42px;
                max-width: 42px;
                min-height: 42px;
                max-height: 42px;
            }

            QPushButton#tool:hover {
                background: #383C47;
            }

            QPushButton#toolActive {
                background: #E95420;
                border: 1px solid #E95420;
                border-radius: 10px;
                margin=0px;
                color: white;
                min-width: 42px;
                max-width: 42px;
                min-height: 42px;
                max-height: 42px;
            }

            /* ---------- AI buttons ---------- */

            QPushButton#aiButton {
                background: #2C313A;
                border: 1px solid #3A3F4B;
                border-radius: 10px;
                padding: 10px;
                text-align: left;
                color: #E6E6E6;
            }

            QPushButton#aiButton:hover {
                background: #383C47;
                border-color: #E95420;
            }

            /* ---------- Tool buttons ---------- */

            QToolButton {
                background: transparent;
                border: none;
                color: #9AA0A6;
                padding: 4px;
            }

            QToolButton:hover {
                color: white;
            }
            QToolTip {
                background-color: #FFF8C6;   /* light warm yellow */
                color: #202020;              /* dark text */
                border: 1px solid #C9B458;
                padding: 6px 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }



        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

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
        self.labels_layout.setContentsMargins(0, 0, 0, 0)
        self.labels_layout.setSpacing(4)

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
        self.rect_btn.setStyleSheet("""
            QPushButton {
                text-align: bottom center;
                padding-top: 0px;
                padding-bottom: 2px;
            }
        """)

        self.poly_btn = QPushButton()
        self.poly_btn.setIcon(QIcon("./resources/icons/tools/pentagon.png"))
        self.poly_btn.setFixedSize(btn_size, btn_size)
        self.poly_btn.setIconSize(QSize(icon_size, icon_size))
        self.poly_btn.setFont(QFont("Arial", 14))
        self.poly_btn.setToolTip("Polygon Tool")
        self.poly_btn.clicked.connect(lambda: self.set_tool("polygon"))
        self.poly_btn.setStyleSheet("""
            QPushButton {
                text-align: bottom center;
                padding-top: 0px;
                padding-bottom: 2px;
            }
        """)

        tools.addWidget(self.rect_btn)
        tools.addWidget(self.poly_btn)
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
        """
        Set the active annotation tool and update the UI accordingly.

        Args:
            tool (str): Tool name ('rectangle' or 'polygon')
        """
        self.current_tool = tool

        self.rect_btn.setObjectName("toolActive" if tool == "rectangle" else "tool")
        self.poly_btn.setObjectName("toolActive" if tool == "polygon" else "tool")

        for btn in [self.rect_btn, self.poly_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.toolChanged.emit(tool)


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
        self.name_btn.setStyleSheet(
            """
                QPushButton:hover {
                        background: #383C47;
                        border-color: #E95420;
                    }
            """
        )
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

        self.setStyleSheet(f"""
            QPushButton {{
                text-align:left;
                padding:8px;
                border-radius:8px;
                color:#333;
            }}

            QPushButton:hover {{
                background:#ECECF2;
            }}
        """)