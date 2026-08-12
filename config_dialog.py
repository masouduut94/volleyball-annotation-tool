"""
Configuration Dialog Module for VB Annotator

This module provides the configuration dialog interface, allowing users to configure application
settings including AI model paths and label management.

Key Features:
- AI model configuration with file browsing
- Model path management and persistence
- Tabbed interface for organized settings
"""

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
    """
    Configuration dialog for managing application settings.

    This dialog provides a user interface for configuring various aspects of the
    VB Annotator application, including AI model paths and label definitions.
    Settings are persisted through the database manager.

    Attributes:
        db (DatabaseManager): Database manager instance for persisting settings
        selected_color (str): Currently selected color in hex format (e.g., "#00FF00")
        model_labels (dict): Dictionary mapping model keys to their path label widgets

    Signals:
        (Inherits QDialog signals)
    """

    def __init__(self, db: DatabaseManager, parent=None):
        """
        Initialize the Configuration Dialog.

        Args:
            db (DatabaseManager): Database manager instance for accessing and
                                 persisting configuration settings
            parent: Parent widget (optional)
        """
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
        """
        Build the main user interface for the configuration dialog.

        This method creates the tabbed interface and populates it with
        configuration panels for different categories of settings.
        """
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        self.tabs.addTab(
            self._create_ai_tab(),
            "AI Models",
        )

        layout.addWidget(self.tabs)

    def _create_ai_tab(self):
        """
        Create the AI Models configuration tab.

        This tab displays a list of AI model types with their current paths
        and provides browse buttons for updating the paths. Each model type
        has a label showing the current path and a browse button to select
        a new model file.

        Returns:
            QWidget: The configured AI Models tab widget
        """
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
        """
        Open a file dialog to browse for a YOLO model file.

        This method opens a file selection dialog filtered for PyTorch model
        files (.pt), updates the database with the selected path, and updates
        the label widget to display the new path.

        Args:
            key (str): The model identifier key (e.g., "ball", "court")
            label_widget (QLabel): The label widget to update with the selected path
        """
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
