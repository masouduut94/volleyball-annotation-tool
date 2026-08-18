# main_window.py (updated version)

from typing import Optional

import cv2
import numpy as np
from PyQt6.QtGui import QPixmap, QImage, QShortcut, QKeySequence
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
    QMessageBox, QDialog
)

from graphics_view import GraphicsView
from graphics_scene import AnnotationScene, ToolMode
from database.db import DatabaseManager
from config_dialog import ConfigDialog
from services.auto_annotator import AutoAnnotator
from services.batch_inference import BatchInferenceDialog
from services.yolo_exporter import YOLOExporter
from ui.left_sidebar import LeftSideBar
from ui.top_toolbar import TopToolbar
from ui.bottom_toolbar import BottomToolbar
from ui.utils import information_box
from ui.right_sidebar import RightSidebar, SectionHeader
from vb_gui.vb_annotator.database.data import Label, Annotation, Layer
from PyQt6.QtWidgets import QMessageBox

from ui.export_dialog import YOLOExportDialog

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
        QShortcut(QKeySequence("Q"), self, activated=self.previous_15_frame)
        QShortcut(QKeySequence("E"), self, activated=self.next_15_frame)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_annotations)
        QShortcut(QKeySequence("Shift+Delete"), self, activated=self.clear_current_frame_annotations)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self.open_batch_inference)

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _create_ui(self):
        # ---------------------------------------------------------
        # Scene / View
        # ---------------------------------------------------------

        self.scene = AnnotationScene(self.db)

        self.view = GraphicsView()
        self.view.setScene(self.scene)

        self.view.setMinimumWidth(960)

        self.scene.set_current_layer(
            self.current_layer
        )

        # ---------------------------------------------------------
        # Top toolbar
        # ---------------------------------------------------------

        self.top_toolbar = TopToolbar(self)
        self.addToolBar(self.top_toolbar)

        # ---------------------------------------------------------
        # Side / bottom toolbars
        # ---------------------------------------------------------

        self.left_toolbar = self._create_left_toolbar()

        self.bottom_toolbar = BottomToolbar(self)
        # self.bottom_toolbar.setMinimumHeight(250)

        self.bottom_toolbar.previousFrame.connect(
            self.previous_frame
        )

        self.bottom_toolbar.nextFrame.connect(
            self.next_frame
        )

        self.bottom_toolbar.gotoFrame.connect(
            self.goto_frame
        )

        # ---------------------------------------------------------
        # Right AI sidebar
        # ---------------------------------------------------------

        self.right_sidebar = self._create_right_sidebar()

        # IMPORTANT:
        # Keep the AI sidebar fixed so it doesn't steal
        # horizontal space from the image.
        self.right_sidebar.setFixedWidth(280)

        # ---------------------------------------------------------
        # Central widget
        # ---------------------------------------------------------

        central = QWidget()
        self.setCentralWidget(central)

        central.setStyleSheet(
            """
            QWidget {
                background-color: #1E1F24;
            }
            """
        )

        main_layout = QVBoxLayout(central)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        # ---------------------------------------------------------
        # Main content
        # ---------------------------------------------------------

        content_layout = QHBoxLayout()

        content_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.setSpacing(0)

        # Left toolbar
        content_layout.addWidget(self.left_toolbar, 0)

        # Image view

        # Stretch = 1 means:
        # "Give the view all remaining horizontal space."
        content_layout.addWidget(self.view, 1)

        content_layout.addWidget(self.right_sidebar, 0)

        main_layout.addLayout(content_layout, 1)

        # Bottom toolbar
        main_layout.addWidget(self.bottom_toolbar, 0)

    def _create_left_toolbar(self):
        self.left_toolbar = LeftSideBar(self.db)
        self.left_toolbar.layerChanged.connect(self.layer_changed)
        self.left_toolbar.labelChanged.connect(self.label_changed)
        self.left_toolbar.toolChanged.connect(self.tool_changed)

        self.activate_rectangle()

        # Layers option
        self.left_toolbar.visibilityChanged.connect(
            self.layer_visibility_changed
        )

        return self.left_toolbar

    def _create_right_sidebar(self):
        self.right_sidebar = RightSidebar(
            model_status=self.get_ai_model_status(),
            parent=self,
        )

        self.right_sidebar.detectRequested.connect(
            self.run_ai_detection
        )

        self.right_sidebar.configureJobRequested.connect(
            self.open_batch_inference
        )

        self.right_sidebar.settingsRequested.connect(
            self.open_config
        )

        return self.right_sidebar

    def get_ai_model_status(self):
        """
        Return whether the required AI models are configured.

        Returns:
            dict:
                {
                    "ball": bool,
                    "players": bool,
                    "actions": bool,
                }
        """

        return {
            "ball": self.auto_annotator.ensure_loaded("ball"),
            "players": self.auto_annotator.ensure_loaded("players"),
            "actions": self.auto_annotator.ensure_loaded("actions"),
        }

    def open_config(self):
        dialog = ConfigDialog(self.db, self)
        if dialog.exec():
            self.refresh_ai_sidebar()

    def refresh_ai_sidebar(self):
        """
        Refresh the green/status indicators in the AI sidebar.
        """

        if not hasattr(self, "right_sidebar"):
            return

        self.right_sidebar.model_status = (
            self.get_ai_model_status()
        )

        self.right_sidebar.refresh_status()

    def run_ai_detection(self, model_name):
        """
        Run AI detection for the current frame.
        """

        # ---------------------------------------------------------
        # Make sure the model exists
        # ---------------------------------------------------------

        if not self.auto_annotator.ensure_loaded(model_name):
            QMessageBox.warning(
                self,
                "AI Model Not Configured",
                (
                    f"The {model_name} model has not been configured.\n\n"
                    "Please open Settings and configure the model first."
                ),
            )

            self.open_config()
            return

        # ---------------------------------------------------------
        # Map model -> layer
        # ---------------------------------------------------------

        layer_map = {
            "ball": "ball",
            "players": "players",
            "actions": "actions",
        }

        layer_name = layer_map.get(model_name)

        if not layer_name:
            QMessageBox.warning(
                self,
                "Unknown Model",
                f"Unknown AI model: {model_name}",
            )
            return

        # ---------------------------------------------------------
        # Run inference
        # ---------------------------------------------------------

        self.run_layer_ai(
            model_name,
            layer_name,
        )

    def run_layer_ai(self, layer_name, model_key):
        self.left_toolbar.set_layer(layer_name)
        self.auto_annotate(model_key)

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

        self.bottom_toolbar.set_frame_range(len(files) - 1)

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

        self.bottom_toolbar.set_frame_range(self.total_frames - 1)

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

        # Update bottom toolbar
        self.bottom_toolbar.set_current_frame(frame_number)

    # ---------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------

    def next_frame(self):
        if self.cap is not None:
            if self.bottom_toolbar.get_current_frame() < self.total_frames - 1:
                self.bottom_toolbar.set_current_frame(
                    self.bottom_toolbar.get_current_frame() + 1
                )
                self.goto_frame(self.bottom_toolbar.get_current_frame())
        elif self.image_paths:
            if self.current_index < len(self.image_paths) - 1:
                self.current_index += 1
                self.bottom_toolbar.set_current_frame(self.current_index)
                self.load_current_image()

    def next_15_frame(self):
        if self.cap is not None:
            if self.bottom_toolbar.get_current_frame() < self.total_frames - 15:
                self.bottom_toolbar.set_current_frame(
                    self.bottom_toolbar.get_current_frame() + 15
                )
                self.goto_frame(self.bottom_toolbar.get_current_frame())
        elif self.image_paths:
            if self.current_index < len(self.image_paths) - 15:
                self.current_index += 15
                self.bottom_toolbar.set_current_frame(self.current_index)
                self.load_current_image()

    def previous_frame(self):
        if self.bottom_toolbar.get_current_frame() > 0:
            new_frame = self.bottom_toolbar.get_current_frame() - 1
            self.bottom_toolbar.set_current_frame(new_frame)
            if self.cap is not None:
                self.goto_frame(new_frame)
            elif self.image_paths:
                self.current_index = new_frame
                self.load_current_image()

    def previous_15_frame(self):
        if self.bottom_toolbar.get_current_frame()-15 > 0:
            new_frame = self.bottom_toolbar.get_current_frame() - 15
            self.bottom_toolbar.set_current_frame(new_frame)
            if self.cap is not None:
                self.goto_frame(new_frame)
            elif self.image_paths:
                self.current_index = new_frame
                self.load_current_image()

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
                self.bottom_toolbar.get_current_frame(),
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

    def run_batch_inference_on_frame(self, frame_number, model_keys):
        imported_total = 0
        frame = self.get_frame_by_number(frame_number)

        for model_key in model_keys:
            result = self.auto_annotator.predict(
                model_key,
                frame,
            )

            layer = self.db.get_layer(model_key)

            annotations, imported = self.convert_result_to_annotations(result, layer)
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

                if layer.name == 'players' and name == 'person':
                    name = 'player'

                if name not in labels:
                    continue

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                annotations.append(
                    Annotation(
                        media_name=path,
                        frame_number=frame_number,
                        shape_type='rectangle',
                        label=labels[name],
                        layer=layer,
                        geometry={"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
                    )
                )
                imported += 1

        # Segmentation
        if result.masks is not None:
            for mask, cls in zip(result.masks.xy, result.boxes.cls):
                name = result.names[int(cls)].lower()

                if layer.name == 'players' and name == 'person':
                    name = 'player'

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

    def export_yolo(self):

        dialog = YOLOExportDialog(
            self.db,
            self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        settings = dialog.get_settings()

        if not settings:
            return

        try:

            exporter = YOLOExporter(
                self.db
            )

            exporter.export(
                output_dir=settings["output_dir"],
                mode=settings["mode"],
                output_format=settings["format"],
                selected_layers=settings["layers"],
                selected_labels=settings["labels"],
                selected_videos=settings["videos"],
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not export dataset:\n\n{e}",
            )

            return

        QMessageBox.information(
            self,
            "Export Complete",
            "YOLO dataset was exported successfully.",
        )
