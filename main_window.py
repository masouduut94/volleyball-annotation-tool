from typing import Optional

import cv2
import numpy as np
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
    QMessageBox
)

from graphics_view import GraphicsView
from graphics_scene import AnnotationScene, ToolMode
from database.db import DatabaseManager
from config_dialog import ConfigDialog
from services.auto_annotator import AutoAnnotator
from services.batch_inference import BatchInferenceDialog
from ui.layer_sidebar import LayerSidebar
from ui.tools import information_box
from vb_gui.vb_annotator.database.data import Label, Annotation, Layer


class MainWindow(QMainWindow):
    def __init__(self, db_path: str = "annotations.db"):
        super().__init__()

        self.original_frame = None
        self.setWindowTitle("Volleyball Annotation Platform")
        self.resize(1200, 800)

        self.db = DatabaseManager(db_path=db_path)
        self.auto_annotator = AutoAnnotator(self.db)

        self.image_paths = []
        self.current_index = 0

        self.video_path = None
        self.cap = None
        self.total_frames = 0

        self.original_width = 960
        self.original_height = 540

        self.current_layer = "court"
        self.current_label = "net"

        self.visible_layers = {
            "court": True,
            "players": True,
            "ball": True,
            "actions": True,
        }

        self._create_ui()

        QShortcut(QKeySequence("A"), self, activated=self.previous_frame)
        QShortcut(QKeySequence("D"), self, activated=self.next_frame)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_annotations)
        QShortcut(QKeySequence("Shift+Delete"), self, activated=self.clear_current_frame_annotations)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self.open_batch_inference)

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _create_ui(self):
        self.scene = AnnotationScene(self.db)
        self.view = GraphicsView()
        self.view.setScene(self.scene)
        self.scene.set_current_layer(
            self.current_layer,
        )

        self._create_top_toolbar()
        self._create_left_toolbar()

        central = QWidget()
        self.setCentralWidget(central)
        self.setStyleSheet(
            """
            background-color: #1E1F24;
            """
        )

        main_layout = QVBoxLayout(central)
        content_layout = QHBoxLayout()

        content_layout.addWidget(self.left_toolbar)
        content_layout.addWidget(self.view, 1)

        main_layout.addLayout(content_layout)
        main_layout.addWidget(self._create_bottom_bar())

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

        # AI Batch Inference
        batch_action = QAction("AI Batch Inference", self)
        batch_action.triggered.connect(self.open_batch_inference)
        toolbar.addAction(batch_action)

    def open_config(self):
        dialog = ConfigDialog(self.db, self)
        dialog.exec()

    def _create_left_toolbar(self):
        self.left_toolbar = LayerSidebar(self.db)
        self.left_toolbar.layerChanged.connect(self.layer_changed)
        self.left_toolbar.labelChanged.connect(self.label_changed)
        self.left_toolbar.toolChanged.connect(self.tool_changed)

        self.activate_rectangle()

        # Layers option
        self.left_toolbar.visibilityChanged.connect(
            self.layer_visibility_changed
        )

        # Auto-annotate adjustment for automatic layer change.

        self.left_toolbar.detect_court_btn.clicked.connect(
            lambda: self.run_layer_ai("court", "court")
        )

        self.left_toolbar.detect_players_btn.clicked.connect(
            lambda: self.run_layer_ai("players", "players")
        )

        self.left_toolbar.detect_ball_btn.clicked.connect(
            lambda: self.run_layer_ai("ball", "ball")
        )

        self.left_toolbar.detect_actions_btn.clicked.connect(
            lambda: self.run_layer_ai("actions", "actions")
        )

    def run_layer_ai(self, layer_name, model_key):
        self.left_toolbar.set_layer(layer_name)
        self.auto_annotate(model_key)

    def _create_bottom_bar(self):
        # Create container widget for styling
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-top: 1px solid #3c3c3c;
                padding: 5px 10px;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #666;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666;
                border-color: #3c3c3c;
            }
            QSpinBox {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 12px;
                min-width: 80px;
            }
            QSpinBox:hover {
                border-color: #666;
            }
            QSpinBox:focus {
                border-color: #4a90d9;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3c3c3c;
                border: none;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a4a4a;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 12px;
            }
            QLabel#total_label {
                color: #888;
                font-weight: 300;
            }
            QLabel#frame_label {
                color: #888;
                font-weight: 300;
                margin-right: 4px;
            }
            QLabel#separator_label {
                color: #555;
                font-weight: 300;
                margin: 0 2px;
            }
        """)

        layout = QHBoxLayout(bottom_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # --- Navigation buttons with icons ---
        prev_btn = QPushButton("◀ Previous")
        prev_btn.setToolTip("Previous frame (A)")
        prev_btn.clicked.connect(self.previous_frame)

        next_btn = QPushButton("Next ▶")
        next_btn.setToolTip("Next frame (D)")
        next_btn.clicked.connect(self.next_frame)

        # --- Separator ---
        separator1 = QLabel("|")
        separator1.setObjectName("separator_label")

        # --- Frame navigation with spin box ---
        frame_label = QLabel("Frame")
        frame_label.setObjectName("frame_label")

        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(0)
        self.frame_spin.setToolTip("Jump to frame number")
        self.frame_spin.valueChanged.connect(self.goto_frame)

        # --- Total frames display ---
        separator2 = QLabel("/")
        separator2.setObjectName("separator_label")

        self.total_label = QLabel("0")
        self.total_label.setObjectName("total_label")

        # --- Spacer to push everything to the left ---
        layout.addWidget(prev_btn)
        layout.addWidget(next_btn)
        layout.addWidget(separator1)
        layout.addWidget(frame_label)
        layout.addWidget(self.frame_spin)
        layout.addWidget(separator2)
        layout.addWidget(self.total_label)
        layout.addStretch()

        return bottom_widget

    # ---------------------------------------------------------
    # Tools
    # ---------------------------------------------------------

    def layer_visibility_changed(self, layer, visible):
        self.visible_layers[layer] = visible
        self.reload_visible_layers()

    def reload_visible_layers(self):
        path, _, frame = self.current_media_info()

        if path is None:
            return

        # Clear all rendered annotation items
        self.scene.clear_annotations()

        # Clear label registry in the scene
        self.scene.layer_labels.clear()

        for layer_name, visible in self.visible_layers.items():
            if not visible:
                continue

            layer = self.db.get_layer(layer_name)

            if layer is None:
                continue

            # Register labels for this layer
            labels = layer.labels

            self.scene.set_layer_labels(layer.name, labels)

            # Load annotations for this layer
            annotations = self.db.load_annotations(
                media_path=path,
                layer_id=layer.layer_id,
                frame_number=frame,
            )

            self.scene.load_annotations(annotations=annotations, layer_name=layer_name)

        # Update the scene's active layer
        self.scene.set_current_layer(self.current_layer)

        # Emit a single update notification
        self.scene.annotation_changed.emit()

    def activate_rectangle(self):
        self.left_toolbar.rect_btn.setChecked(True)
        self.left_toolbar.poly_btn.setChecked(False)
        self.scene.set_tool(ToolMode.RECTANGLE)

    def activate_polygon(self):
        self.left_toolbar.rect_btn.setChecked(False)
        self.left_toolbar.poly_btn.setChecked(True)
        self.scene.set_tool(ToolMode.POLYGON)
        # self.update_tool_buttons()

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
        frame = self.get_frame_by_number(frame_number)
        if frame is None:
            QMessageBox.warning(
                self,
                "No frame",
                "Please load an image or video first.",
            )
            return
        self.original_frame = frame.copy()

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
        """
        It gives access to 3 things:
        - video_path/image_paths
        - media_type "video/image"
        - frame_number if it's video type
        Returns:

        """
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
        layer = self.db.get_layer(self.current_layer)

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
            layer=layer,
            frame_number=frame,
            annotations=self.scene.export_annotations(self.current_layer, path, frame),
        )

        # self.statusBar().showMessage("Annotations saved successfully.", 3000)  # 3 seconds
        information_box(self, message="✅ Annotations saved successfully.")

    def load_annotations(self):
        path, _, frame = self.current_media_info()

        if path is None:
            return

        layer = self.db.get_layer(self.current_layer)

        if layer is None:
            return

        annotations = self.db.load_annotations(
            media_path=path,
            layer_id=layer.layer_id,
            frame_number=frame,
        )

        self.scene.load_annotations(
            annotations=annotations,
            layer_name=self.current_layer
        )

    def layer_changed(self, layer_name):
        self.current_layer = layer_name
        self.scene.set_current_layer(layer_name)
        self.scene.clear_annotations()
        self.load_annotations()

    def label_changed(self, label_name):
        self.current_label = label_name
        layer = self.db.get_layer(self.current_layer)
        labels = {label.name: label for label in layer.labels}

        color = labels[label_name].color

        self.scene.set_current_label(
            label_name,
            color,
        )

    def tool_changed(self, tool_name):
        if tool_name == "rectangle":
            self.activate_rectangle()
        elif tool_name == "polygon":
            self.activate_polygon()

    def clear_current_frame_annotations(self):
        path, media_type, frame = self.current_media_info()
        layer = self.db.get_layer(self.current_layer)

        if path is None:
            return

        self.scene.clear_annotations()

        self.db.delete_annotations(
            media_path=path,
            layer_id=layer.layer_id,
            frame_number=frame,
        )

    def auto_annotate(self, model_key):
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

        layer = self.db.get_layer(self.current_layer)
        imported = self.scene.import_yolo_result(
            result,
            layer,
            self.original_width,
            self.original_height
        )

        if imported == 0:
            QMessageBox.information(
                self,
                "No matching labels",
                (
                    "The model produced detections, but none of the detected "
                    "class names match the labels defined for the active layer."
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

    def get_frame_by_number(self, frame_number: int) -> Optional[np.ndarray]:
        if self.cap is None:
            if self.image_paths and frame_number < len(self.image_paths):
                path = self.image_paths[frame_number]
                image = cv2.imread(path)
                return image

        self.cap.set(
            cv2.CAP_PROP_POS_FRAMES,
            frame_number,
        )

        ok, frame = self.cap.read()

        if not ok:
            return None

        return frame

    def run_batch_inference_on_frame(
            self,
            frame_number,
            model_keys,
    ):
        imported_total = 0
        frame = self.get_frame_by_number(frame_number)

        for model_key in model_keys:
            result = self.auto_annotator.predict(
                model_key,
                frame,
            )

            layer = self.db.get_layer(model_key)

            annotations, imported = self.convert_result_to_annotations(result, layer)

            layer = self.db.get_layer(model_key)
            path, media_type, _ = self.current_media_info()

            if len(annotations) == 0:
                continue

            self.db.save_annotations(
                media_path=path,
                media_type=media_type,
                width=self.original_width,
                height=self.original_height,
                layer=layer,
                frame_number=frame_number,
                annotations=annotations,
            )

            imported_total += imported

        return imported_total

    def open_batch_inference(self):
        if self.video_path is None and len(self.image_paths) == 0:
            QMessageBox.warning(
                self,
                "No media loaded",
                "Please open a video or image sequence first.",
            )
            return

        dialog = BatchInferenceDialog(
            db=self.db,
            auto_annotator=self.auto_annotator,
            main_window=self,
            parent=self,
        )

        dialog.exec()

    def convert_result_to_annotations(self, result, layer: Layer):
        imported = 0
        annotations = []
        path, media_type, frame_number = self.current_media_info()
        labels = {label.name: label for label in layer.labels}
        # Detection
        if result.boxes is not None:
            for box in result.boxes:

                cls = int(box.cls[0])
                name = result.names[cls].lower()

                if name not in labels:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                Annotation(
                    media_name=path,
                    frame_number=frame_number,
                    shape_type='rectangle',
                    label=labels[name],
                    layer=layer,
                    geometry={"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
                )
                imported += 1

        # Segmentation
        if result.masks is not None:
            for mask, cls in zip(result.masks.xy, result.boxes.cls):
                name = result.names[int(cls)].lower()

                if name not in labels:
                    continue

                annotations.append(
                    Annotation(
                        media_name=path,
                        frame_number=frame_number,
                        shape_type='polygon',
                        label=labels[name],
                        layer=layer,
                        geometry=[[float(x), float(y)] for x, y in mask]
                    )
                )

                imported += 1
        return annotations, imported
