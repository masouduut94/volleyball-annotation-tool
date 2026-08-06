from pathlib import Path
import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QPixmap, QImage, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QFileDialog,
    QPushButton,
    QSpinBox,
    QLabel,
    QComboBox,
    QMessageBox
)

from graphics_view import GraphicsView
from graphics_scene import AnnotationScene, ToolMode
from database.db import DatabaseManager
from config_dialog import ConfigDialog
from services.auto_annotator import AutoAnnotator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.original_frame = None
        self.setWindowTitle("Volleyball Annotation Platform")
        self.resize(1200, 800)

        self.db = DatabaseManager()
        self.auto_annotator = AutoAnnotator(self.db)

        self.current_job = self.db.get_jobs()[0]

        self.image_paths = []
        self.current_index = 0

        self.video_path = None
        self.cap = None
        self.total_frames = 0

        self.original_width = 960
        self.original_height = 540

        self._create_ui()

        QShortcut(QKeySequence("A"), self, activated=self.previous_frame)
        QShortcut(QKeySequence("D"), self, activated=self.next_frame)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_annotations)

        QShortcut(
            QKeySequence("Shift+Delete"),
            self,
            activated=self.clear_current_frame_annotations
        )

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _create_ui(self):
        self.scene = AnnotationScene()
        self.view = GraphicsView()
        self.view.setScene(self.scene)

        self._create_top_toolbar()
        self._create_left_toolbar()

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        content_layout = QHBoxLayout()

        content_layout.addWidget(self.left_toolbar)
        content_layout.addWidget(self.view, 1)

        main_layout.addLayout(content_layout)
        main_layout.addLayout(self._create_bottom_bar())

    def _create_top_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        open_images = QAction("Open Images", self)
        open_images.triggered.connect(self.open_images)
        toolbar.addAction(open_images)

        open_video = QAction("Open Video", self)
        open_video.triggered.connect(self.open_video)
        toolbar.addAction(open_video)

        clear = QAction("Clear", self)
        clear.triggered.connect(self.scene.clear_annotations)
        toolbar.addAction(clear)

        save = QAction("Save", self)
        save.triggered.connect(self.save_annotations)
        toolbar.addAction(save)

        config = QAction("Config", self)
        config.triggered.connect(self.open_config)
        toolbar.addAction(config)

    def open_config(self):
        dialog = ConfigDialog(self.db, self)
        dialog.exec()

        self.refresh_jobs_and_labels()

    def _create_left_toolbar(self):
        self.left_toolbar = QWidget()
        layout = QVBoxLayout(self.left_toolbar)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(10)

        # ---------------------------- # Job selector # ----------------------------
        layout.addWidget(QLabel("Job"))
        self.job_combo = QComboBox()
        self.job_combo.currentIndexChanged.connect(self.job_changed)
        layout.addWidget(self.job_combo)
        # ---------------------------- # Label selector # ----------------------------
        layout.addWidget(QLabel("Label"))
        self.label_combo = QComboBox()
        self.label_combo.currentIndexChanged.connect(self.label_changed)
        layout.addWidget(self.label_combo)
        layout.addSpacing(15)
        # ---------------------------- # Rectangle tool # ----------------------------
        self.rect_btn = QPushButton("Rectangle")
        self.rect_btn.setCheckable(True)
        self.rect_btn.setChecked(True)
        self.rect_btn.clicked.connect(self.activate_rectangle)
        layout.addWidget(self.rect_btn)
        # ---------------------------- # Polygon tool # ----------------------------
        self.poly_btn = QPushButton("Polygon")
        self.poly_btn.setCheckable(True)
        self.poly_btn.clicked.connect(self.activate_polygon)
        layout.addWidget(self.poly_btn)
        layout.addStretch()
        self.refresh_jobs_and_labels()

        layout.addSpacing(20)

        layout.addWidget(QLabel("Auto-Annotate"))

        self.ball_btn = QPushButton("Ball")
        self.ball_btn.clicked.connect(self.auto_annotate_ball)
        layout.addWidget(self.ball_btn)

        self.court_btn = QPushButton("Court")
        self.court_btn.clicked.connect(self.auto_annotate_court)
        layout.addWidget(self.court_btn)

        self.actions_btn = QPushButton("Actions")
        self.actions_btn.clicked.connect(self.auto_annotate_actions)
        layout.addWidget(self.actions_btn)

        self.players_btn = QPushButton("Players")
        self.players_btn.clicked.connect(self.auto_annotate_players)
        layout.addWidget(self.players_btn)

    def _create_bottom_bar(self):
        layout = QHBoxLayout()

        prev_btn = QPushButton("Previous")
        prev_btn.clicked.connect(self.previous_frame)

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.next_frame)

        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(0)
        self.frame_spin.valueChanged.connect(self.goto_frame)

        self.total_label = QLabel("/ 0")

        layout.addWidget(prev_btn)
        layout.addWidget(next_btn)
        layout.addWidget(QLabel("Frame:"))
        layout.addWidget(self.frame_spin)
        layout.addWidget(self.total_label)
        layout.addStretch()

        return layout

    # ---------------------------------------------------------
    # Tools
    # ---------------------------------------------------------

    def activate_rectangle(self):
        self.rect_btn.setChecked(True)
        self.poly_btn.setChecked(False)
        self.scene.set_tool(ToolMode.RECTANGLE)

    def activate_polygon(self):
        self.rect_btn.setChecked(False)
        self.poly_btn.setChecked(True)
        self.scene.set_tool(ToolMode.POLYGON)

    # ---------------------------------------------------------
    # Image loading
    # ---------------------------------------------------------

    def open_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )

        if not files:
            return

        self.cap = None
        self.video_path = None

        self.image_paths = files
        self.current_index = 0

        self.frame_spin.setMaximum(len(files) - 1)
        self.total_label.setText(f"/ {len(files)}")

        self.load_current_image()

    def load_current_image(self):
        if not self.image_paths:
            return

        path = self.image_paths[self.current_index]

        image = cv2.imread(path)
        self.original_frame = image
        if image is None:
            return

        self.original_height, self.original_width = image.shape[:2]

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (960, 540))

        qimage = QImage(
            image.data,
            image.shape[1],
            image.shape[0],
            image.strides[0],
            QImage.Format.Format_RGB888,
        )

        self.scene.set_image(QPixmap.fromImage(qimage))
        self.scene.set_image_scale(
            self.original_width,
            self.original_height,
        )

        self.view.fit_image()

        self.load_annotations()

    # ---------------------------------------------------------
    # Video loading
    # ---------------------------------------------------------

    def open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Videos (*.mp4 *.avi *.mov *.mkv)",
        )

        if not path:
            return

        self.image_paths = []

        self.video_path = path
        self.cap = cv2.VideoCapture(path)

        self.total_frames = int(
            self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        )

        self.frame_spin.setMaximum(self.total_frames - 1)
        self.total_label.setText(f"/ {self.total_frames}")

        self.goto_frame(0)

    def goto_frame(self, frame_number):
        if self.cap is None:
            if self.image_paths:
                self.current_index = frame_number
                self.load_current_image()
            return

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        ok, frame = self.cap.read()
        self.original_frame = frame

        if not ok:
            return

        self.original_height, self.original_width = frame.shape[:2]

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (960, 540))

        qimage = QImage(
            frame.data,
            frame.shape[1],
            frame.shape[0],
            frame.strides[0],
            QImage.Format.Format_RGB888,
        )

        self.scene.set_image(QPixmap.fromImage(qimage))
        self.scene.set_image_scale(
            self.original_width,
            self.original_height,
        )

        self.view.fit_image()

        self.load_annotations()

    # ---------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------

    def next_frame(self):
        if self.cap is not None:
            if self.frame_spin.value() < self.total_frames - 1:
                self.frame_spin.setValue(self.frame_spin.value() + 1)
        elif self.image_paths:
            if self.current_index < len(self.image_paths) - 1:
                self.frame_spin.setValue(self.current_index + 1)

    def previous_frame(self):
        if self.frame_spin.value() > 0:
            self.frame_spin.setValue(self.frame_spin.value() - 1)

    # ---------------------------------------------------------
    # Save / Load
    # ---------------------------------------------------------

    def current_media_info(self):
        if self.cap is not None:
            return (
                self.video_path,
                "video",
                self.frame_spin.value(),
            )

        if self.image_paths:
            return (
                self.image_paths[self.current_index],
                "image",
                None,
            )

        return None, None, None

    def save_annotations(self):
        path, media_type, frame = self.current_media_info()

        if path is None:
            QMessageBox.warning(
                self,
                "No Media",
                "Please open an image or video first.",
            )
            return

        self.db.save_annotations(
            media_path=path,
            media_type=media_type,
            width=self.original_width,
            height=self.original_height,
            job_id=self.current_job.id,
            frame_number=frame,
            annotations=self.scene.export_annotations(),
        )

        # self.statusBar().showMessage("Annotations saved successfully.", 3000)  # 3 seconds
        message_label = QLabel("✅ Annotations saved successfully.", self)
        message_label.setStyleSheet(
            "background-color: #333; color: white; padding: 20px 20px; "
            "border-radius: 5px; font-size: 20px;"
        )
        message_label.adjustSize()
        message_label.move(
            (self.width() - message_label.width()) // 2,
            50
        )
        message_label.show()
        QTimer.singleShot(3000, message_label.hide)

    def load_annotations(self):
        path, _, frame = self.current_media_info()

        if path is None:
            return

        annotations = self.db.load_annotations(
            media_path=path,
            job_id=self.current_job_id,
            frame_number=frame,
        )

        self.scene.load_annotations(annotations)

    def refresh_jobs_and_labels(self):
        """ Reload job and label dropdowns after configuration changes. Preserve the current job if it still exists. """

        previous_job_id = getattr(self, "current_job_id", None)

        self.job_combo.blockSignals(True)
        self.job_combo.clear()

        jobs = self.db.get_jobs()

        selected_index = -1

        for index, job in enumerate(jobs):
            self.job_combo.addItem(job.name, job.id)

            if job.id == previous_job_id:
                selected_index = index

        if jobs:
            if selected_index == -1:
                selected_index = 0

                self.job_combo.setCurrentIndex(selected_index)
                self.current_job_id = self.job_combo.currentData()
        else:
            self.current_job_id = None

        self.job_combo.blockSignals(False)

        self.load_labels()

    def job_changed(self, index):
        if index < 0:
            return

        self.current_job_id = self.job_combo.currentData()

        self.load_labels()

        # Clear current scene
        self.scene.clear_annotations()

        # Load annotations only for this job
        self.load_annotations()

    def load_labels(self):
        previous_label_name = None

        if getattr(self, "current_label", None):
            previous_label_name = self.current_label.name

        self.label_combo.blockSignals(True)
        self.label_combo.clear()

        if self.current_job_id is None:
            self.current_label = None
            self.label_combo.blockSignals(False)
            return

        labels = self.db.get_labels(self.current_job_id)

        available_labels = {}

        selected_index = -1

        for index, label in enumerate(labels):
            self.label_combo.addItem(label.name, label)
            available_labels[label.name] = label.color

            if label.name == previous_label_name:
                selected_index = index

        self.scene.set_available_labels(available_labels)

        if labels:
            if selected_index == -1:
                selected_index = 0
            self.label_combo.setCurrentIndex(selected_index)
            self.current_label = self.label_combo.currentData()
            self.scene.set_current_label(
                self.current_label.name,
                self.current_label.color
            )
        else:
            self.current_label = None

        self.label_combo.blockSignals(False)

    def label_changed(self, index):
        if index < 0:
            return

        label = self.label_combo.currentData()

        if label is None:
            return

        self.current_label = label

        self.scene.set_current_label(
            label.name,
            label.color
        )

    def clear_current_frame_annotations(self):
        path, media_type, frame = self.current_media_info()

        if path is None:
            return

        self.scene.clear_annotations()

        self.db.delete_annotations(
            media_path=path,
            job_id=self.current_job_id,
            frame_number=frame,
        )

    def auto_annotate(self, model_key):
        if self.current_job_id is None:
            QMessageBox.warning(
                self,
                "No job",
                "Please select a job first.",
            )
            return

        frame = self.original_frame

        if frame is None:
            QMessageBox.warning(
                self,
                "No frame",
                "Please load an image or video first.",
            )
            return

        try:
            result = self.auto_annotator.predict(model_key, frame)

        except RuntimeError as e:
            QMessageBox.warning(
                self,
                "Model not configured",
                str(e),
            )
            return

        job_labels = {
            label.name.lower(): label
            for label in self.db.get_labels(self.current_job_id)
        }

        imported = self.scene.import_yolo_result(
            result,
            job_labels,
            self.original_width,
            self.original_height,
        )

        if imported == 0:
            QMessageBox.information(
                self,
                "No matching labels",
                (
                    "The model produced detections, but none of the detected "
                    "class names match the labels defined for the current job."
                ),
            )

    def auto_annotate_ball(self):
        self.auto_annotate("ball")

    def auto_annotate_court(self):
        self.auto_annotate("court")

    def auto_annotate_actions(self):
        self.auto_annotate("actions")

    def auto_annotate_players(self):
        self.auto_annotate("players")


