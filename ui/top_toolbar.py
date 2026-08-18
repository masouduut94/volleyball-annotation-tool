from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QToolBar, QMenu


class TopToolbar(QToolBar):
    """
    Top toolbar for the main window providing file operations and configuration access.

    This toolbar contains actions for:
    - Opening images/videos
    - Clearing annotations
    - Saving annotations
    - Configuration dialog
    - AI batch inference
    """

    def __init__(self, parent=None):
        """
        Initialize the top toolbar.

        Args:
            parent: Parent widget (typically the main window)
        """
        super().__init__(parent)

        # Store parent reference for signal connections
        self.main_window = parent

        # Create actions
        self._create_actions()

        # Add actions to toolbar
        self._add_actions_to_toolbar()

    def _create_actions(self):
        self.open_images_action = QAction(
            "Open Images",
            self,
        )

        self.open_images_action.triggered.connect(
            self.main_window.open_images
        )

        self.open_video_action = QAction(
            "Open Video",
            self,
        )

        self.open_video_action.triggered.connect(
            self.main_window.open_video
        )

        self.clear_action = QAction(
            "Clear",
            self,
        )

        self.clear_action.triggered.connect(
            self.main_window.scene.clear_annotations
        )

        self.save_action = QAction(
            "Save",
            self,
        )

        self.save_action.triggered.connect(
            self.main_window.save_annotations
        )

        # ----------------------------------------------------------
        # Export menu
        # ----------------------------------------------------------

        self.export_menu = QMenu(
            "Export",
            self,
        )

        self.export_yolo_action = QAction(
            "YOLO",
            self,
        )

        self.export_yolo_action.triggered.connect(
            self.main_window.export_yolo
        )

        self.export_menu.addAction(
            self.export_yolo_action
        )

    def _add_actions_to_toolbar(self):
        self.addAction(self.open_images_action)

        self.addAction(self.open_video_action)

        self.addAction(self.clear_action)

        self.addAction(self.save_action)

        self.addSeparator()

        self.addAction(self.export_menu.menuAction())
