from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QToolBar, QMenu


class TopToolbar(QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._create_actions()
        self._add_actions_to_toolbar()

    def _create_actions(self):
        self.open_images_action = QAction("Open Images", self)
        self.open_images_action.triggered.connect(self.main_window.open_images)
        self.open_video_action = QAction("Open Video", self)
        self.open_video_action.triggered.connect(self.main_window.open_video)
        self.clear_action = QAction("Clear", self)
        self.clear_action.triggered.connect(self.main_window.scene.clear_annotations)
        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self.main_window.save_annotations)

        # ----------------------------------------------------------
        # Export menu
        # ----------------------------------------------------------

        self.export_menu = QMenu("Export", self)

        self.export_yolo_action = QAction("YOLO", self)
        self.export_yolo_action.triggered.connect(self.main_window.export_yolo)
        self.export_menu.addAction(self.export_yolo_action)

        # NEW — VideoMAE clip dataset export
        self.export_videomae_action = QAction("VideoMAE", self)
        self.export_videomae_action.triggered.connect(self.main_window.export_videomae)
        self.export_menu.addAction(self.export_videomae_action)

    def _add_actions_to_toolbar(self):
        self.addAction(self.open_images_action)
        self.addAction(self.open_video_action)
        self.addAction(self.clear_action)
        self.addAction(self.save_action)
        self.addSeparator()
        self.addAction(self.export_menu.menuAction())
