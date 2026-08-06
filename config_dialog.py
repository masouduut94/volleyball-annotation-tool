from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
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
        self.load_jobs()

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        self.tabs.addTab(
            self._create_annotation_tab(),
            "Annotation",
        )

        self.tabs.addTab(
            self._create_ai_tab(),
            "AI Models",
        )

        layout.addWidget(self.tabs)

    def _create_annotation_tab(self):
        widget = QWidget()

        main_layout = QHBoxLayout(widget)

        # ---------------- Jobs panel ----------------
        jobs_panel = QVBoxLayout()

        jobs_panel.addWidget(QLabel("Jobs"))

        self.jobs_list = QListWidget()
        self.jobs_list.currentItemChanged.connect(
            self.on_job_changed
        )
        jobs_panel.addWidget(self.jobs_list)

        self.job_name = QLineEdit()
        self.job_name.setPlaceholderText("Job name")
        jobs_panel.addWidget(self.job_name)

        job_btn_row = QHBoxLayout()

        add_job = QPushButton("Add")
        add_job.clicked.connect(self.add_job)

        remove_job = QPushButton("Remove")
        remove_job.clicked.connect(self.remove_job)

        job_btn_row.addWidget(add_job)
        job_btn_row.addWidget(remove_job)

        jobs_panel.addLayout(job_btn_row)

        # ---------------- Labels panel ----------------
        labels_panel = QVBoxLayout()

        labels_panel.addWidget(QLabel("Labels"))

        self.labels_list = QListWidget()
        labels_panel.addWidget(self.labels_list)

        self.label_name = QLineEdit()
        self.label_name.setPlaceholderText("Label name")
        labels_panel.addWidget(self.label_name)

        color_row = QHBoxLayout()

        self.color_preview = QWidget()
        self.color_preview.setFixedSize(28, 28)
        self._update_color_preview()

        color_btn = QPushButton("Color")
        color_btn.clicked.connect(self.choose_color)

        color_row.addWidget(self.color_preview)
        color_row.addWidget(color_btn)
        color_row.addStretch()

        labels_panel.addLayout(color_row)

        label_btn_row = QHBoxLayout()

        add_label = QPushButton("Add")
        add_label.clicked.connect(self.add_label)

        remove_label = QPushButton("Remove")
        remove_label.clicked.connect(self.remove_label)

        label_btn_row.addWidget(add_label)
        label_btn_row.addWidget(remove_label)

        labels_panel.addLayout(label_btn_row)

        # ---------------- Add both panels ----------------
        main_layout.addLayout(jobs_panel, 1)
        main_layout.addLayout(labels_panel, 1)

        return widget

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
    # Jobs
    # ---------------------------------------------------------

    def load_jobs(self):
        self.jobs_list.clear()

        jobs = self.db.get_jobs()

        for job in jobs:
            item = QListWidgetItem(job.name)
            item.setData(Qt.ItemDataRole.UserRole, job.id)
            self.jobs_list.addItem(item)

        if self.jobs_list.count():
            self.jobs_list.setCurrentRow(0)

    def on_job_changed(self, current, previous):
        self.load_labels()

    def current_job_id(self):
        item = self.jobs_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def add_job(self):
        name = self.job_name.text().strip()

        if not name:
            return

        try:
            self.db.add_job(name)
        except Exception:
            QMessageBox.warning(
                self,
                "Error",
                "Job already exists.",
            )

        self.job_name.clear()
        self.load_jobs()

    def remove_job(self):
        job_id = self.current_job_id()

        if job_id is None:
            return

        reply = QMessageBox.question(
            self,
            "Remove Job",
            "Delete selected job and all its annotations?",
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.db.remove_job(job_id)
            self.load_jobs()

    # ---------------------------------------------------------
    # Labels
    # ---------------------------------------------------------

    def load_labels(self):
        self.labels_list.clear()

        job_id = self.current_job_id()

        if job_id is None:
            return

        labels = self.db.get_labels(job_id)

        for label in labels:
            item = QListWidgetItem(label.name)
            item.setData(Qt.ItemDataRole.UserRole, label.id)
            item.setForeground(QColor(label.color))
            self.labels_list.addItem(item)

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.selected_color), self)

        if color.isValid():
            self.selected_color = color.name()
            self._update_color_preview()

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(
            f"background:{self.selected_color}; border:1px solid #555;"
        )

    def add_label(self):
        job_id = self.current_job_id()

        if job_id is None:
            return

        name = self.label_name.text().strip()

        if not name:
            return

        try:
            self.db.add_label(
                job_id,
                name,
                self.selected_color,
            )
        except Exception:
            QMessageBox.warning(
                self,
                "Error",
                "Label already exists.",
            )

        self.label_name.clear()
        self.load_labels()

    def remove_label(self):
        item = self.labels_list.currentItem()

        if item is None:
            return

        label_id = item.data(Qt.ItemDataRole.UserRole)

        self.db.remove_label(label_id)
        self.load_labels()