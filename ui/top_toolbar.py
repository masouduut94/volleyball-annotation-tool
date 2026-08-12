from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QToolBar


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
        """Create all toolbar actions."""
        self.open_images_action = QAction("Open Images", self)
        self.open_images_action.triggered.connect(self.main_window.open_images)

        self.open_video_action = QAction("Open Video", self)
        self.open_video_action.triggered.connect(self.main_window.open_video)

        self.clear_action = QAction("Clear", self)
        self.clear_action.triggered.connect(self.main_window.scene.clear_annotations)

        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self.main_window.save_annotations)

        self.config_action = QAction("Config", self)
        self.config_action.triggered.connect(self.main_window.open_config)

        self.batch_action = QAction("AI Batch Inference", self)
        self.batch_action.triggered.connect(self.main_window.open_batch_inference)

    def _add_actions_to_toolbar(self):
        """Add all actions to the toolbar."""
        self.addAction(self.open_images_action)
        self.addAction(self.open_video_action)
        self.addAction(self.clear_action)
        self.addAction(self.save_action)
        self.addAction(self.config_action)
        self.addAction(self.batch_action)