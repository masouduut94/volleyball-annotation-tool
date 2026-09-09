import cv2
import numpy as np
from typing import Optional

from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtGui import QPixmap, QImage, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
                             QDialog, QMessageBox)

from graphics_view import GraphicsView
from graphics_scene import AnnotationScene, ToolMode

from database.db import DatabaseManager
from database.data import Annotation, Layer

from services.auto_annotator import AutoAnnotator
from services.game_state_worker import GameStateWorker
from services.yolo_export_worker import YOLOExportWorker
from services.batch_inference import BatchInferenceDialog
from services.game_state_classifier import GameStateClassifier

from ui.utils import information_box
from ui.top_toolbar import TopToolbar
from ui.left_sidebar import LeftSideBar
from ui.right_sidebar import RightSidebar
from ui.bottom_toolbar import BottomToolbar
from ui.confirmation_bar import ConfirmationBar
from ui.game_state_dialog import GameStateRangeDialog
from ui.export_progress_dialog import ExportProgressDialog
from ui.export_dialog import YOLOExportDialog, ExportSummaryDialog
from ui.temporal_timeline import TemporalTimelinePanel

class MainWindow(QMainWindow):
    def __init__(self, db_path: str = "annotations.db"):
        super().__init__()

        self.original_frame = None
        self.setWindowTitle("Volleyball Annotation Platform")
        self.resize(1200, 800)

        self.db = DatabaseManager(db_path=db_path)
        # Auto-Annotators (YOLO + VideoMAE)
        self.auto_annotator = AutoAnnotator(self.db)
        self.game_state_classifier = GameStateClassifier()
        gs_path = self.db.get_model_path("game_state")
        if gs_path:
            self.game_state_classifier.ensure_loaded(gs_path)

        self.image_paths = []
        self.current_index = 0

        self.video_path = None
        self.cap = None
        self.total_frames = 0

        # ---------------------------------------------------------
        # Video Playback
        # ---------------------------------------------------------

        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self._play_next_frame)

        self.is_playing = False
        self.video_fps = 30.0

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

        self._tag_pending_start = None
        self._tag_pending_state = None

        self._create_ui()

        # Bottom toolbar
        QShortcut(QKeySequence("A"), self, activated=self.previous_frame)
        QShortcut(QKeySequence("D"), self, activated=self.next_frame)
        QShortcut(QKeySequence("Q"), self, activated=self.previous_15_frame)
        QShortcut(QKeySequence("E"), self, activated=self.next_15_frame)
        QShortcut(QKeySequence("Space"), self, activated=self.toggle_playback)

        # Top toolbar
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_annotations)
        QShortcut(QKeySequence("Shift+Delete"), self, activated=self.clear_current_frame_annotations)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, activated=self.open_batch_inference)

        # Redo/Undo
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.redo)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.confirm_current_frame)

        # Left Toolbar
        QShortcut(QKeySequence("Esc"), self, activated=self.set_tool_to_none)
        QShortcut(QKeySequence("P"), self, activated=self.activate_polygon)
        QShortcut(QKeySequence("R"), self, activated=self.activate_rectangle)
        QShortcut(QKeySequence("Alt+1"), self, activated=self.cycle_layer)
        QShortcut(QKeySequence("Alt+2"), self, activated=self.cycle_frame_label)
        QShortcut(QKeySequence("Alt+3"), self, activated=self.cycle_video_label)
    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _create_ui(self):
        self.scene = AnnotationScene(self.db)
        self.view = GraphicsView()
        self.view.setScene(self.scene)
        self.view.setMinimumWidth(960)
        self.scene.set_current_layer(self.current_layer)

        # Refresh the confirmation bar any time annotations change
        # (manual edit/delete or AI import) while this frame is open.
        self.scene.annotation_changed.connect(self.refresh_frame_confirmation_indicator)

        self.top_toolbar = TopToolbar(self)
        self.addToolBar(self.top_toolbar)

        self.left_toolbar = self._create_left_toolbar()
        self.bottom_toolbar = BottomToolbar(self)
        self.bottom_toolbar.previousFrame.connect(self.previous_frame)
        self.bottom_toolbar.nextFrame.connect(self.next_frame)
        self.bottom_toolbar.gotoFrame.connect(self.goto_frame)

        self.timeline_panel = TemporalTimelinePanel()
        self.timeline_panel.seekRequested.connect(self.goto_frame)
        self.timeline_panel.applyChangesRequested.connect(self.on_timeline_apply_clicked)
        self.timeline_panel.intervalDeleteRequested.connect(self.on_timeline_interval_delete_requested)
        self.timeline_panel.setVisible(False)

        self.right_sidebar = self._create_right_sidebar()

        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("QWidget { background-color: #1E1F24; }")

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # NEW — confirmation bar + view stacked vertically, so it always
        # sits directly above the "main frame" being edited.
        self.confirmation_bar = ConfirmationBar()
        self.confirmation_bar.confirmRequested.connect(self.confirm_current_frame)

        view_container = QWidget()
        view_layout = QVBoxLayout(view_container)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(0)
        view_layout.addWidget(self.confirmation_bar)
        view_layout.addWidget(self.view, 1)

        content_layout.addWidget(self.left_toolbar, 0)
        content_layout.addWidget(view_container, 1)  # was: self.view directly
        content_layout.addWidget(self.right_sidebar, 0)

        main_layout.addLayout(content_layout, 1)
        main_layout.addWidget(self.bottom_toolbar, 0)
        main_layout.addWidget(self.timeline_panel, 0)

    def _create_left_toolbar(self):
        self.left_toolbar = LeftSideBar(self.db)
        self.left_toolbar.layerChanged.connect(self.layer_changed)
        self.left_toolbar.labelChanged.connect(self.label_changed)
        self.left_toolbar.toolChanged.connect(self.tool_changed)

        self.left_toolbar.videoMarkStartRequested.connect(self.tag_mark_start)
        self.left_toolbar.videoMarkEndRequested.connect(self.tag_mark_end)
        self.left_toolbar.videoCancelRequested.connect(self.tag_cancel)
        self.deactivate_tools()

        return self.left_toolbar

    def _create_right_sidebar(self):
        self.right_sidebar = RightSidebar(
            model_status=self.get_ai_model_status(),
            model_paths=self.get_ai_model_paths(),
            parent=self,
        )
        self.right_sidebar.detectRequested.connect(self.run_ai_detection)
        self.right_sidebar.configureJobRequested.connect(self.open_batch_inference)
        self.right_sidebar.setPathRequested.connect(self.set_model_path)
        self.right_sidebar.gameStateDetectRequested.connect(self.open_game_state_dialog)

        return self.right_sidebar

    def refresh_ai_sidebar(self):
        if not hasattr(self, "right_sidebar"):
            return
        self.right_sidebar.model_status = self.get_ai_model_status()
        self.right_sidebar.model_paths = self.get_ai_model_paths()
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

        self.run_layer_ai(model_name, layer_name)

    def run_layer_ai(self, layer_name, model_key):
        self.left_toolbar.set_layer(layer_name)
        self.auto_annotate(model_key)

    def activate_rectangle(self):
        self.left_toolbar.sync_tool_visuals("rectangle")
        self.scene.set_tool(ToolMode.RECTANGLE)

    def activate_polygon(self):
        self.left_toolbar.sync_tool_visuals("polygon")
        self.scene.set_tool(ToolMode.POLYGON)

    def deactivate_tools(self):
        self.left_toolbar.clear_tool_selection()
        self.scene.set_tool(ToolMode.NONE)

    def on_scene_tool_mode_changed(self, mode: str):
        if mode == ToolMode.NONE:
            self.left_toolbar.clear_tool_selection()

    def cycle_layer(self):
        self.left_toolbar.cycle_layer()

    def cycle_frame_label(self):
        self.left_toolbar.cycle_frame_label()

    def cycle_video_label(self):
        self.left_toolbar.cycle_video_label()

    # ---------------------------------------------------------
    # Image loading
    # ---------------------------------------------------------

    def open_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open Images", "", "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not files:
            return

        self.pause_playback()
        self.cap = None
        self.video_path = None

        self.image_paths = files
        self.current_index = 0

        self.bottom_toolbar.set_frame_range(len(files) - 1)
        self.timeline_panel.setVisible(False)
        self.load_game_state_segments()  # NEW — clears any leftover overlay from a prior video

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
        self.scene.set_image_scale(self.original_width, self.original_height)
        self.scene.set_media_context(path, "image", None)

        self.view.fit_image()

        self.load_annotations()
        self.refresh_frame_confirmation_indicator()
        self.refresh_tag_editing_state()

    def get_frame_by_number(self, frame_number: int) -> Optional[np.ndarray]:
        if self.cap is None:
            if self.image_paths and frame_number < len(self.image_paths):
                path = self.image_paths[frame_number]
                image = cv2.imread(path)
                return image

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        ok, frame = self.cap.read()

        if not ok:
            return None

        return frame

    # ---------------------------------------------------------
    # Video loading
    # ---------------------------------------------------------

    def open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", "Videos (*.mp4 *.avi *.mov *.mkv)",
        )
        if not path:
            return

        self.pause_playback()
        self.image_paths = []

        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.video_fps <= 0:
            self.video_fps = 20.0

        self.bottom_toolbar.set_frame_range(self.total_frames - 1)
        self.timeline_panel.set_max_frame(self.total_frames - 1)
        self.timeline_panel.set_fps(self.video_fps)
        self.timeline_panel.setVisible(True)

        self.goto_frame(0)
        self.load_game_state_segments()

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
        self.scene.set_image_scale(self.original_width, self.original_height)
        self.scene.set_media_context(self.video_path, "video", frame_number)
        self.view.fit_image()
        self.load_annotations()

        # Update bottom toolbar
        self.bottom_toolbar.set_current_frame(frame_number)
        self.timeline_panel.set_current_frame(frame_number)
        self.refresh_frame_confirmation_indicator()

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
        self.pause_playback()
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
        self.pause_playback()
        if self.bottom_toolbar.get_current_frame() > 0:
            new_frame = self.bottom_toolbar.get_current_frame() - 1
            self.bottom_toolbar.set_current_frame(new_frame)
            if self.cap is not None:
                self.goto_frame(new_frame)
            elif self.image_paths:
                self.current_index = new_frame
                self.load_current_image()

    def previous_15_frame(self):
        self.pause_playback()
        if self.bottom_toolbar.get_current_frame() - 15 > 0:
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
            return self.image_paths[self.current_index], "image", None

        return None, None, None

    def save_annotations(self):
        path, media_type, frame = self.current_media_info()
        layer = self.db.get_layer(self.current_layer)

        if path is None:
            QMessageBox.warning(self, "No Media", "Please open an image or video first.")
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

        # A single Save also commits any pending video-annotation (game-state)
        # timeline edits, so the user doesn't need to separately hit "Apply
        # Changes" on the timeline first.
        video_edits = self.timeline_panel.get_pending_edits()
        if video_edits:
            self._write_video_annotation_edits(video_edits)

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

        self.scene.load_annotations(annotations, self.current_layer)

    def layer_changed(self, layer_name):
        self.current_layer = layer_name
        self.scene.set_current_layer(layer_name)
        self.scene.clear_annotations()
        self.load_annotations()
        self.refresh_frame_confirmation_indicator()

    def label_changed(self, label_name):
        self.current_label = label_name
        layer = self.db.get_layer(self.current_layer)
        labels = {label.name: label for label in layer.labels}

        color = labels[label_name].color

        self.scene.set_current_label(label_name, color)

    def tool_changed(self, tool_name):
        """Only reached via LeftSideBar.set_tool's emit — i.e. an actual button click."""
        if tool_name == "rectangle":
            self.activate_rectangle()
        elif tool_name == "polygon":
            self.activate_polygon()
        elif tool_name == "none":
            self.deactivate_tools()

    def set_tool_to_none(self):
        self.left_toolbar.set_tool("none")
        self.scene.cancel_polygon()
        self.scene.set_tool(ToolMode.NONE)

    def clear_current_frame_annotations(self):
        path, media_type, frame = self.current_media_info()
        layer = self.db.get_layer(self.current_layer)
        if path is None:
            return

        self.scene.clear_annotations(self.current_layer)
        self.db.delete_annotations(media_path=path, layer_id=layer.layer_id, frame_number=frame)
        self.refresh_frame_confirmation_indicator()

    # ---------------------------------------------------------
    # Undo/Redo Manager
    # ---------------------------------------------------------

    def undo(self):
        self.scene.undo_stack.undo()

    def redo(self):
        self.scene.undo_stack.redo()

    def auto_annotate(self, model_key):
        frame = self.original_frame
        if frame is None:
            QMessageBox.warning(self, "No frame", "Please load an image or video first.")
            return

        try:
            result = self.auto_annotator.predict(model_key, frame)
        except RuntimeError as e:
            QMessageBox.warning(self, "Model not configured", str(e))
            return

        layer = self.db.get_layer(self.current_layer)
        path, media_type, frame_number = self.current_media_info()

        imported = self.scene.import_yolo_result(
            result, layer, self.original_width, self.original_height,
            path, media_type, frame_number,  # NEW args
        )

        self.refresh_frame_confirmation_indicator()  # NEW — AI import resets review state

        if imported == 0:
            QMessageBox.information(
                self, "No matching labels",
                "The model produced detections, but none of the detected "
                "class names match the labels defined for the active layer.",
            )

    def confirm_current_frame(self):
        path, media_type, frame = self.current_media_info()
        if path is None:
            return
        layer = self.db.get_layer(self.current_layer)
        self.db.confirm_frame(path, layer.layer_id, frame)
        self.refresh_frame_confirmation_indicator()

    def refresh_frame_confirmation_indicator(self):
        path, media_type, frame = self.current_media_info()
        if path is None:
            self.confirmation_bar.set_confirmed(False, "", "")
            return

        layer = self.db.get_layer(self.current_layer)
        confirmed = self.db.is_frame_confirmed(path, layer.layer_id, frame)
        frame_label = f"Frame {frame}" if frame is not None else "Image"
        self.confirmation_bar.set_confirmed(confirmed, self.current_layer, frame_label)

    def run_batch_inference_on_frame(self, frame_number, model_keys):
        imported_total = 0
        frame = self.get_frame_by_number(frame_number)

        for model_key in model_keys:
            result = self.auto_annotator.predict(model_key, frame)

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
                        media_name=path, frame_number=frame_number,
                        shape_type='rectangle', label=labels[name], layer=layer,
                        geometry={"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                        is_ai_generated=True, confirmed=False
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

    # ------------------------------------------
    # YOLO worker methods
    # ------------------------------------------

    def export_yolo(self):

        dialog = YOLOExportDialog(self.db, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        settings = dialog.get_settings()
        if not settings:
            return

        self._export_settings = settings
        self.export_progress_dialog = ExportProgressDialog(self)
        self.export_thread = QThread(self)
        self.export_worker = YOLOExportWorker(self.db, settings)
        self.export_worker.moveToThread(self.export_thread)

        # ----------------------------------------------------------
        # Signals
        # ----------------------------------------------------------

        self.export_thread.started.connect(self.export_worker.run)

        self.export_worker.progress.connect(self.export_progress_dialog.set_progress)

        self.export_progress_dialog.cancel_button.clicked.connect(self.export_worker.cancel)

        self.export_worker.finished.connect(self._export_finished)

        self.export_worker.cancelled.connect(self._export_cancelled)

        self.export_worker.error.connect(self._export_error)

        # Cleanup.
        self.export_worker.finished.connect(self.export_thread.quit)

        self.export_worker.cancelled.connect(self.export_thread.quit)

        self.export_worker.error.connect(self.export_thread.quit)

        self.export_thread.finished.connect(self.export_worker.deleteLater)

        self.export_thread.finished.connect(self.export_thread.deleteLater)

        # ----------------------------------------------------------
        # Start
        # ----------------------------------------------------------

        self.export_progress_dialog.show()

        self.export_thread.start()

    def _export_finished(self, stats):

        self.export_progress_dialog.set_finished()
        self.export_progress_dialog.close()
        ExportSummaryDialog(self._export_settings, stats, self).exec()

    def _export_cancelled(self):

        self.export_progress_dialog.set_cancelled()

        self.export_progress_dialog.close()

    def _export_error(self, message):

        self.export_progress_dialog.close()

        QMessageBox.critical(
            self,
            "Export Failed",
            f"Could not export YOLO dataset:\n\n{message}",
        )

    # ------------------------------------------
    # VideoMAE Worker methods
    # ------------------------------------------

    def open_game_state_dialog(self):
        if self.video_path is None:
            QMessageBox.warning(
                self, "No video loaded",
                "Game-state classification needs a loaded video (it's not meaningful on a loose image set).",
            )
            return

        if not self.game_state_classifier.is_configured():
            QMessageBox.warning(self, "Model Not Configured", "Please set the Game State model path first.")
            self.set_model_path("game_state")
            if not self.game_state_classifier.is_configured():
                return

        dialog = GameStateRangeDialog(
            max_frame=self.total_frames - 1,
            current_frame=self.bottom_toolbar.get_current_frame(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        settings = dialog.get_settings()

        self.game_state_progress_dialog = ExportProgressDialog(
            self,
            window_title="Classifying Game State",
            preparing_text=(
                f"Preparing classification for frames "
                f"{settings['start_frame']}–{settings['end_frame']}..."
            ),
            progress_verb="Classifying",
            finished_text="Classification completed.",
            cancelled_text="Classification cancelled.",
            error_text="Classification failed.",
        )

        self.game_state_thread = QThread(self)
        self.game_state_worker = GameStateWorker(
            db=self.db,
            classifier=self.game_state_classifier,
            video_path=self.video_path,
            media_type="video",
            width=self.original_width,
            height=self.original_height,
            start_frame=settings["start_frame"],
            end_frame=settings["end_frame"],
            window_size=settings["window_size"],
        )
        self.game_state_worker.moveToThread(self.game_state_thread)

        self.game_state_thread.started.connect(self.game_state_worker.run)
        self.game_state_worker.progress.connect(
            lambda done, total: self.game_state_progress_dialog.set_progress(
                int(done / max(total, 1) * 100), detail=f"window {done}/{total}"
            )
        )
        self.game_state_progress_dialog.cancel_button.clicked.connect(self.game_state_worker.cancel)
        self.game_state_worker.finished.connect(self._game_state_finished)
        self.game_state_worker.cancelled.connect(self._game_state_cancelled)
        self.game_state_worker.error.connect(self._game_state_error)

        self.game_state_worker.finished.connect(self.game_state_thread.quit)
        self.game_state_worker.cancelled.connect(self.game_state_thread.quit)
        self.game_state_worker.error.connect(self.game_state_thread.quit)
        self.game_state_thread.finished.connect(self.game_state_worker.deleteLater)
        self.game_state_thread.finished.connect(self.game_state_thread.deleteLater)

        self.game_state_progress_dialog.show()
        self.game_state_thread.start()

    def _game_state_finished(self, count):
        self.game_state_progress_dialog.set_finished()
        self.game_state_progress_dialog.close()
        self.load_game_state_segments()
        information_box(self, message=f"✅ Classified {count} window(s).")

    def _game_state_cancelled(self):
        self.game_state_progress_dialog.set_cancelled()
        self.game_state_progress_dialog.close()

    def _game_state_error(self, message):
        self.game_state_progress_dialog.close()
        QMessageBox.critical(self, "Classification Failed", f"Could not classify game state:\n\n{message}")

    def load_game_state_segments(self):
        if self.video_path is None:
            self.bottom_toolbar.set_game_state_segments([])
            self.timeline_panel.set_segments([])
            return
        segments = self.db.get_game_state_segments(self.video_path)
        self.bottom_toolbar.set_game_state_segments(
            [(s.start_frame, s.end_frame, s.state, s.source) for s in segments]
        )
        self.timeline_panel.set_segments(segments)

    def get_ai_model_paths(self):
        return {
            "ball": self.db.get_model_path("ball"),
            "players": self.db.get_model_path("players"),
            "actions": self.db.get_model_path("actions"),
            "game_state": self.db.get_model_path("game_state"),
        }

    def get_ai_model_status(self):
        return {
            "ball": self.auto_annotator.is_configured("ball"),
            "players": self.auto_annotator.is_configured("players"),
            "actions": self.auto_annotator.is_configured("actions"),
            "game_state": self.game_state_classifier.is_configured(),
        }

    def set_model_path(self, model_key):
        if model_key == "game_state":
            # Use folder dialog for game_state
            folder_path = QFileDialog.getExistingDirectory(
                self,
                caption=f"Select {model_key} model folder",
                directory=""
            )
            if not folder_path:
                return

            path = folder_path
        else:
            # Use file dialog for other models
            path, _ = QFileDialog.getOpenFileName(
                self,
                caption=f"Select {model_key} model",
                directory="",
                filter="Model files (*.pt *.onnx);;All Files (*)"
            )
            if not path:
                return

        self.db.set_model_path(model_key, path)
        if model_key == "game_state":
            self.game_state_classifier.ensure_loaded(path)
        self.refresh_ai_sidebar()

    def tag_mark_start(self, state):
        if self.video_path is None:
            QMessageBox.warning(self, "No video loaded", "Tagging needs a loaded video.")
            return
        self._tag_pending_start = self.bottom_toolbar.get_current_frame()
        self._tag_pending_state = state
        self.left_toolbar.set_video_tag_pending(True, self._tag_pending_start, state)
        self.timeline_panel.set_pending_marker(self._tag_pending_start, state)

    def tag_mark_end(self):
        if self._tag_pending_start is None:
            return

        end_frame = self.bottom_toolbar.get_current_frame()
        start_frame, end_frame = sorted((self._tag_pending_start, end_frame))

        self.db.save_manual_game_state_segment(
            media_path=self.video_path,
            media_type="video",
            width=self.original_width,
            height=self.original_height,
            start_frame=start_frame,
            end_frame=end_frame,
            state=self._tag_pending_state,
        )

        self._tag_pending_start = None
        self._tag_pending_state = None
        self.left_toolbar.set_video_tag_pending(False)
        self.timeline_panel.set_pending_marker(None, None)
        self.load_game_state_segments()

    def tag_cancel(self):
        self._tag_pending_start = None
        self._tag_pending_state = None
        self.left_toolbar.set_video_tag_pending(False)
        self.timeline_panel.set_pending_marker(None, None)

    def _write_video_annotation_edits(self, edits: dict) -> int:
        """
        Writes each (segment_id -> (start, end)) pair to the DB, preserving
        each segment's existing label, then refreshes the timeline/slider.
        Returns the number of segments actually written.
        """
        if not edits or self.video_path is None:
            return 0

        segments = self.db.get_game_state_segments(self.video_path)
        by_id = {s.segment_id: s for s in segments}
        written = 0

        for segment_id, (start_frame, end_frame) in edits.items():
            seg = by_id.get(segment_id)
            if seg is None:
                continue
            error = self.db.update_game_state_segment(segment_id, start_frame, end_frame, seg.state)
            if error:
                QMessageBox.warning(self, "Could Not Update Tag", error)
                continue
            written += 1

        self.load_game_state_segments()
        return written

    def on_timeline_apply_clicked(self, edits: dict):
        """User explicitly clicked 'Apply Changes' on the timeline panel."""
        written = self._write_video_annotation_edits(edits)
        if written:
            information_box(self, message="✅ Video annotations saved successfully.")

    def on_timeline_interval_edited(self, segment_id, start_frame, end_frame):
        """Timeline drag only changes the range, never the label, so look up
        the segment's current state and keep it."""
        if self.video_path is None:
            return
        segments = self.db.get_game_state_segments(self.video_path)
        match = next((s for s in segments if s.segment_id == segment_id), None)
        if match is None:
            return

        error = self.db.update_game_state_segment(segment_id, start_frame, end_frame, match.state)
        if error:
            QMessageBox.warning(self, "Could Not Update Tag", error)
        self.load_game_state_segments()

    def on_timeline_interval_delete_requested(self, segment_id):
        # Commit any other pending drags first, so deleting one box doesn't
        # silently discard unrelated in-progress edits on other boxes.
        pending = self.timeline_panel.get_pending_edits()
        if pending:
            self._write_video_annotation_edits(pending)

        self.db.delete_game_state_segment(segment_id)
        self.load_game_state_segments()

    # ---------------------------------------------------------
    # Video Playback
    # ---------------------------------------------------------

    def toggle_playback(self):
        """
        Toggle between playing and pausing the current video.
        """

        # Playback only makes sense for videos.
        if self.cap is None:
            return

        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()

    def start_playback(self):
        """
        Start video playback.
        """

        if self.cap is None:
            return

        # Do not start playback if we are already playing.
        if self.is_playing:
            return

        # If we are already at the final frame, restart from frame 0.
        current_frame = self.bottom_toolbar.get_current_frame()

        if current_frame >= self.total_frames - 1:
            self.goto_frame(0)

        # Calculate timer interval from video FPS.
        fps = self.video_fps

        if fps <= 0:
            fps = 30.0

        interval_ms = max(1, int(1000 / fps))

        self.playback_timer.start(interval_ms)

        self.is_playing = True

        # Update toolbar appearance.
        self.bottom_toolbar.set_playback_state(True)

    def pause_playback(self):
        """
        Pause video playback.
        """

        if not self.is_playing:
            return

        self.playback_timer.stop()

        self.is_playing = False

        # Restore play icon.
        self.bottom_toolbar.set_playback_state(False)

    def _play_next_frame(self):
        """
        Called automatically by the playback timer.
        """

        if self.cap is None:
            self.pause_playback()
            return

        current_frame = self.bottom_toolbar.get_current_frame()

        # Stop automatically at the final frame.
        if current_frame >= self.total_frames - 1:
            self.pause_playback()
            return

        # Move forward one frame.
        self.next_frame()
