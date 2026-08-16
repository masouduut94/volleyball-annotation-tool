from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PyQt6.QtGui import QIcon, QPixmap


ICON_SIZE = 30

class SectionHeader(QWidget):

    def __init__(
            self,
            title,
            icon_path,
            parent=None,
    ):
        super().__init__(parent)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(2, 4, 2, 6, )

        layout.setSpacing(8)

        icon = QLabel()

        pixmap = QPixmap(icon_path)

        icon.setPixmap(
            pixmap.scaled(
                ICON_SIZE + 20,
                ICON_SIZE + 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        icon.setFixedSize(
            ICON_SIZE + 20,
            ICON_SIZE + 20,
        )

        layout.addWidget(icon)

        label = QLabel(title)

        label.setStyleSheet(
            """
            QLabel {
                color: #F2F2F2;
                font-size: 18px;
                font-weight: bold;
            }
            """
        )

        layout.addWidget(label)

        layout.addStretch()


class DetectionRow(QWidget):
    """
    One AI detection item in the right sidebar.

    Example:

        ✓  Ball segmentation       [Run]

    or

        ✗  Ball segmentation       [Run]
    """

    clicked = pyqtSignal()

    def __init__(self, key, title, icon_path, configured=False, parent=None):
        super().__init__(parent)

        self.key = key
        self.title = title
        self.configured = configured

        self.setup_ui(icon_path)
        self.update_status(configured)

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def setup_ui(self, icon_path):

        self.setObjectName("detectionRow")

        layout = QHBoxLayout(self)

        layout.setContentsMargins(8, 6, 8, 6)

        layout.setSpacing(8)

        # ---------------------------------------------------------
        # Model icon
        # ---------------------------------------------------------

        self.icon_label = QLabel()

        pixmap = QPixmap(icon_path)

        self.icon_label.setPixmap(
            pixmap.scaled(
                ICON_SIZE,
                ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        self.icon_label.setFixedSize(
            ICON_SIZE,
            ICON_SIZE,
        )

        self.icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.icon_label
        )

        # ---------------------------------------------------------
        # Status
        # ---------------------------------------------------------

        self.status_label = QLabel()

        self.status_label.setFixedWidth(16)

        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.status_label
        )

        # ---------------------------------------------------------
        # Name
        # ---------------------------------------------------------

        self.name_label = QLabel(
            self.title
        )

        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout.addWidget(
            self.name_label
        )

        # ---------------------------------------------------------
        # Run
        # ---------------------------------------------------------

        self.run_button = QPushButton(
            "Run"
        )

        self.run_button.setFixedHeight(
            28
        )

        self.run_button.setFixedWidth(
            55
        )

        self.run_button.clicked.connect(
            self.clicked.emit
        )

        layout.addWidget(
            self.run_button
        )

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    def update_status(self, configured):
        self.configured = configured

        if configured:
            self.status_label.setText("✓")
            self.status_label.setStyleSheet(
                """
                QLabel {
                    color: #4CAF50;
                    font-size: 15px;
                    font-weight: bold;
                }
                """
            )

            self.run_button.setEnabled(True)

        else:
            self.status_label.setText("!")
            self.status_label.setStyleSheet(
                """
                QLabel {
                    color: #E0A458;
                    font-size: 15px;
                    font-weight: bold;
                }
                """
            )

            # We still allow clicking the button.
            # MainWindow will show the appropriate error.
            self.run_button.setEnabled(True)


class RightSidebar(QWidget):
    """
    Right-side AI sidebar.

    Responsibilities:
        - Display available AI detectors
        - Show whether their models are configured
        - Trigger single-frame inference
        - Open Configure Job
        - Open Settings

    The actual inference/configuration logic remains in MainWindow.
    """

    detectRequested = pyqtSignal(str)
    configureJobRequested = pyqtSignal()
    settingsRequested = pyqtSignal()

    def __init__(self, model_status=None, parent=None):
        super().__init__(parent)

        self.model_status = model_status or {}

        self.setObjectName("rightSidebar")
        self.setFixedWidth(300)

        self.setup_ui()
        self.refresh_status()

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        # Right AI sidebar
        header = SectionHeader(
            "AI Tools",
            "./resources/icons/right_sidebar/AI.png",
            self,
        )
        # header.setFont(
        #     QFont("Arial", 14, QFont.Weight.Bold)
        # )

        header.setStyleSheet(
            """
            QLabel {
                color: #F2F2F2;
                padding: 4px 2px 8px 2px;
            }
            """
        )

        main_layout.addWidget(header)

        # -----------------------------------------------------
        # Detection section
        # -----------------------------------------------------

        section_title = QLabel("Detection")
        section_title.setFont(
            QFont("Arial", 12, QFont.Weight.Bold)
        )

        section_title.setStyleSheet(
            """
            QLabel {
                color: #AEB4BE;
                padding: 4px 2px;
            }
            """
        )

        main_layout.addWidget(section_title)

        self.ball_row = DetectionRow(
            "ball",
            "Ball segmentation",
            "./resources/icons/right_sidebar/ball.png",
            parent=self,
        )

        self.players_row = DetectionRow(
            "players",
            "Players detection",
            "./resources/icons/right_sidebar/players.png",
            parent=self,
        )

        self.actions_row = DetectionRow(
            "actions",
            "Actions detection",
            "./resources/icons/right_sidebar/actions.png",
            parent=self,
        )

        self.ball_row.clicked.connect(
            lambda: self.detectRequested.emit("ball")
        )

        self.players_row.clicked.connect(
            lambda: self.detectRequested.emit("players")
        )

        self.actions_row.clicked.connect(
            lambda: self.detectRequested.emit("actions")
        )

        main_layout.addWidget(self.ball_row)
        main_layout.addWidget(self.players_row)
        main_layout.addWidget(self.actions_row)

        # -----------------------------------------------------
        # Separator
        # -----------------------------------------------------

        separator = QFrame()
        separator.setFrameShape(
            QFrame.Shape.HLine
        )
        separator.setStyleSheet(
            "color: #343A45;"
        )

        main_layout.addWidget(separator)

        # -----------------------------------------------------
        # Configure Job
        # -----------------------------------------------------

        self.configure_button = QPushButton(
            "Configure Job"
        )

        self.configure_button.setIcon(
            QIcon("./resources/icons/right_sidebar/cycle.png")
        )

        self.configure_button.setIconSize(
            QSize(30, 30)
        )


        self.configure_button.setFixedHeight(38)
        self.configure_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.configure_button.clicked.connect(
            self.configureJobRequested.emit
        )

        main_layout.addWidget(
            self.configure_button
        )

        # -----------------------------------------------------
        # Settings
        # -----------------------------------------------------

        self.settings_button = QPushButton(
            "Settings"
        )

        self.settings_button.setIcon(
            QIcon("./resources/icons/right_sidebar/settings.png")
        )

        self.settings_button.setFixedHeight(38)
        self.settings_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.settings_button.clicked.connect(
            self.settingsRequested.emit
        )

        main_layout.addWidget(
            self.settings_button
        )

        # Push everything to the top
        main_layout.addStretch()

        # -----------------------------------------------------
        # Style
        # -----------------------------------------------------

        self.setStyleSheet(
            """
            QWidget#rightSidebar {
                background: #1E2229;
                border-left: 1px solid #343A45;
            }

            QPushButton {
                background: #2C313A;
                color: #E6E6E6;
                border: 1px solid #3A3F4B;
                border-radius: 7px;
                font-weight: 500;
            }

            QPushButton:hover {
                background: #353B46;
                border-color: #4A5260;
            }

            QPushButton:pressed {
                background: #252A32;
            }
            """
        )

    # ---------------------------------------------------------
    # Model status
    # ---------------------------------------------------------

    def set_model_status(self, model_name, configured):
        """
        Update the status of one detector.

        model_name:
            "ball"
            "players"
            "actions"
        """

        if model_name == "ball":
            self.ball_row.update_status(configured)

        elif model_name == "players":
            self.players_row.update_status(configured)

        elif model_name == "actions":
            self.actions_row.update_status(configured)

    def refresh_status(self):
        """
        Refresh all model status indicators.
        """

        self.set_model_status(
            "ball",
            self.model_status.get("ball", False),
        )

        self.set_model_status(
            "players",
            self.model_status.get("players", False),
        )

        self.set_model_status(
            "actions",
            self.model_status.get("actions", False),
        )
