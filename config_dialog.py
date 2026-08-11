from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QColorDialog,
    QMessageBox,
    QWidget,
    QFileDialog,
    QTabWidget,
)

from database.db import DatabaseManager


class ConfigDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)

        self.db = db
        self.selected_color = "#00FF00"

        self.setWindowTitle("Annotation Configuration")
        self.resize(700, 450)

        self._build_ui()

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        self.tabs.addTab(
            self._create_ai_tab(),
            "AI Models",
        )

        layout.addWidget(self.tabs)

    def _create_ai_tab(self):
        widget = QWidget()

        layout = QVBoxLayout(widget)

        self.model_labels = {}

        models = [
            ("ball", "Ball segmentation"),
            ("court", "Court segmentation"),
            ("actions", "Actions detection"),
            ("players", "Players detection"),
        ]

        for key, title in models:
            row = QHBoxLayout()

            row.addWidget(QLabel(title))

            path_label = QLabel(
                self.db.get_model_path(key)
                or "Not configured"
            )

            path_label.setWordWrap(True)

            browse = QPushButton("Browse")

            browse.clicked.connect(
                lambda checked=False, k=key, lbl=path_label:
                self.browse_model(k, lbl)
            )

            row.addWidget(path_label, 1)
            row.addWidget(browse)

            layout.addLayout(row)

            self.model_labels[key] = path_label

        layout.addStretch()

        return widget

    def browse_model(self, key, label_widget):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YOLO model",
            "",
            "PyTorch (*.pt)",
        )

        if not path:
            return

        self.db.set_model_path(key, path)

        label_widget.setText(path)

    # ---------------------------------------------------------
    # Labels
    # ---------------------------------------------------------
