from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QToolButton
)


class LayerSidebar(QWidget):
    layerChanged = pyqtSignal(str)
    labelChanged = pyqtSignal(str)
    toolChanged = pyqtSignal(str)
    visibilityChanged = pyqtSignal(str, bool)
    lockChanged = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedWidth(260)

        self.current_layer = "court"
        self.current_label = "net"
        self.current_tool = "rectangle"

        self.layer_rows = {}
        self.label_buttons = {}

        self.layer_labels = {
            "court": [
                    ("net", "#4927F5"),
                    ("attack zone", "#128DE5"),
                    ("back zone", "#FFD814"),
                ],
                "players": [
                    ("player", "#27D3F5"),
                    ("libero", "#B027F5"),
                ],
                "ball": [
                    ("ball", "#6CF527"),
                ],
                "actions": [
                    ("spike", "#F5276C"),
                    ("block", "#F5B027"),
                    ("set", "#F54927"),
                    ("receive", "#FFAA00"),
                ],
        }

        self._build_ui()
        self.set_layer("court")
        self.set_tool("rectangle")

    def _build_ui(self):
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
                padding: 8px;
                color: #E6E6E6;
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
                padding: 8px;
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
            row.lockChanged.connect(self.lockChanged.emit)

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

        self.rect_btn = QPushButton("▭")
        self.rect_btn.setFont(QFont("Arial", 14))
        self.rect_btn.clicked.connect(lambda: self.set_tool("rectangle"))

        self.poly_btn = QPushButton("⬡")
        self.poly_btn.setFont(QFont("Arial", 14))
        self.poly_btn.clicked.connect(lambda: self.set_tool("polygon"))

        self.select_btn = QPushButton("🖱")
        self.select_btn.clicked.connect(lambda: self.set_tool("select"))

        tools.addWidget(self.rect_btn)
        tools.addWidget(self.poly_btn)
        tools.addWidget(self.select_btn)
        tools.addStretch()

        layout.addLayout(tools)

        layout.addWidget(self.separator())

        layout.addWidget(self.section("AI Assist"))

        self.detect_court_btn = QPushButton("Detect court")
        self.detect_players_btn = QPushButton("Detect players")
        self.detect_ball_btn = QPushButton("Detect ball")
        self.detect_actions_btn = QPushButton("Suggest actions")
        for btn in [
            self.detect_court_btn,
            self.detect_players_btn,
            self.detect_ball_btn,
            self.detect_actions_btn,
        ]:
            btn.setObjectName("aiButton")

        layout.addWidget(self.detect_court_btn)
        layout.addWidget(self.detect_players_btn)
        layout.addWidget(self.detect_ball_btn)
        layout.addWidget(self.detect_actions_btn)

        layout.addStretch()

    def separator(self):
        line = QFrame()
        line.setObjectName("line")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def section(self, text):
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def set_layer(self, layer):
        self.current_layer = layer
        self.layerChanged.emit(layer)

        for name, row in self.layer_rows.items():
            row.set_active(name == layer)
            # row.style().unpolish(btn)
            # row.style().polish(btn)

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
        self.current_tool = tool

        self.rect_btn.setObjectName("toolActive" if tool == "rectangle" else "tool")
        self.poly_btn.setObjectName("toolActive" if tool == "polygon" else "tool")
        self.select_btn.setObjectName("toolActive" if tool == "select" else "tool")

        for btn in [self.rect_btn, self.poly_btn, self.select_btn]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.toolChanged.emit(tool)



class LayerRow(QWidget):
    clicked = pyqtSignal(str)
    visibilityChanged = pyqtSignal(str, bool)
    lockChanged = pyqtSignal(str, bool)

    def __init__(self, layer_name):
        super().__init__()

        self.layer_name = layer_name
        self.visible = True
        self.locked = False

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

        self.lock_btn = QToolButton()
        self.lock_btn.setText("🔓")
        self.lock_btn.clicked.connect(self.toggle_lock)

        layout.addWidget(self.name_btn, 1)
        layout.addWidget(self.eye_btn)
        layout.addWidget(self.lock_btn)

        self.set_active(False)

    def set_active(self, active):
        if active:
            self.setStyleSheet(
                "background:#E95420; border-radius:8px;"
            )
        else:
            self.setStyleSheet(
                "background:transparent;"
            )

    def toggle_visibility(self):
        self.visible = not self.visible
        self.eye_btn.setText(
            "👁" if self.visible else "🚫"
        )
        self.visibilityChanged.emit(
            self.layer_name,
            self.visible,
        )

    def toggle_lock(self):
        self.locked = not self.locked
        self.lock_btn.setText(
            "🔒" if self.locked else "🔓"
        )
        self.lockChanged.emit(
            self.layer_name,
            self.locked,
        )

class LabelRow(QPushButton):
    def __init__(self, name, color):
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
