from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFrame, QSizePolicy, QComboBox)
from PyQt6.QtGui import QIcon, QPixmap


class SectionHeader(QWidget):

    def __init__(self, title, icon_path, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 6, )
        layout.setSpacing(8)
        icon = QLabel()
        pixmap = QPixmap(icon_path)
        icon.setPixmap(
            pixmap.scaled(
                50,
                50,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        icon.setFixedSize(50, 50)
        layout.addWidget(icon)
        label = QLabel(title)
        label.setObjectName("headerTitle")
        layout.addWidget(label)
        layout.addStretch()


class DetectionRow(QWidget):
    clicked = pyqtSignal()
    pathRequested = pyqtSignal()  # NEW — user wants to (re)set this model's path

    def __init__(
            self,
            key,
            title,
            icon_path,
            icon_size: int,
            configured=False,
            model_path=None,
            parent=None
    ):
        super().__init__(parent)
        self.key = key
        self.title = title
        self.configured = configured
        self.model_path = model_path

        self.setup_ui(icon_path, icon_size)
        self.update_status(configured, model_path)

    def setup_ui(self, icon_path, icon_size):
        self.setObjectName("detectionRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Model icon
        self.icon_label = QLabel()
        pixmap = QPixmap(icon_path)
        self.icon_label.setPixmap(
            pixmap.scaled(icon_size, icon_size,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        )
        self.icon_label.setFixedSize(icon_size, icon_size)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # Status
        self.status_label = QLabel()
        self.status_label.setFixedWidth(16)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Name
        self.name_label = QLabel(self.title)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.name_label)

        # NEW — inline "set model path" button
        self.path_button = QPushButton("…")
        self.path_button.setObjectName("pathButton")
        self.path_button.setFixedSize(28, 28)
        self.path_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path_button.clicked.connect(self.pathRequested.emit)
        layout.addWidget(self.path_button)

        # Run
        self.run_button = QPushButton("Run")
        self.run_button.setFixedHeight(28)
        self.run_button.setFixedWidth(55)
        self.run_button.clicked.connect(self.clicked.emit)
        layout.addWidget(self.run_button)

    def update_status(self, configured, model_path=None):
        self.configured = configured
        if model_path is not None:
            self.model_path = model_path

        self.status_label.setText("✓" if configured else "!")
        self.status_label.setObjectName("statusOk" if configured else "statusWarn")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        self.path_button.setToolTip(self.model_path or "No model path set — click to choose one")
        self.run_button.setEnabled(True)


class GameStateRow(QWidget):
    """
    Row for the video-classification model. Unlike DetectionRow this never
    runs on a single click — "Run" always opens a range picker, because the
    model needs a span of frames, not one.
    """
    runRequested = pyqtSignal()
    pathRequested = pyqtSignal()

    def __init__(
            self,
            icon_path,
            icon_size,
            configured=False,
            model_path=None,
            parent=None
    ):
        super().__init__(parent)
        self.configured = configured
        self.model_path = model_path
        self._setup_ui(icon_path, icon_size)
        self.update_status(configured, model_path)

    def _setup_ui(self, icon_path, icon_size):
        self.setObjectName("detectionRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.icon_label = QLabel()
        pixmap = QPixmap(icon_path)
        self.icon_label.setPixmap(
            pixmap.scaled(
                icon_size,
                icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        self.icon_label.setFixedSize(icon_size, icon_size)
        layout.addWidget(self.icon_label)

        self.status_label = QLabel()
        self.status_label.setFixedWidth(16)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        name_label = QLabel("Game State")
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(name_label)

        self.path_button = QPushButton("…")
        self.path_button.setObjectName("pathButton")
        self.path_button.setFixedSize(28, 28)
        self.path_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path_button.clicked.connect(self.pathRequested.emit)
        layout.addWidget(self.path_button)

        self.run_button = QPushButton("Range…")
        self.run_button.setFixedHeight(28)
        self.run_button.setFixedWidth(65)
        self.run_button.clicked.connect(self.runRequested.emit)
        layout.addWidget(self.run_button)

    def update_status(self, configured, model_path=None):
        self.configured = configured
        if model_path is not None:
            self.model_path = model_path
        self.status_label.setText("✓" if configured else "!")
        self.status_label.setObjectName("statusOk" if configured else "statusWarn")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.path_button.setToolTip(self.model_path or "No model path set — click to choose one")


STATUS_INFO = {
    "none": ("None", "#8A93A3"),
    "ai": ("AI", "#FFD814"),
    "user": ("User", "#2FA6FF"),
    "confirmed": ("Confirmed", "#3DDC84"),
}


class AnnotationStatusRow(QWidget):
    """One layer's row: name, colored status badge, Confirm button."""
    confirmRequested = pyqtSignal(str)  # layer_name

    def __init__(self, layer_name, display_name, parent=None):
        super().__init__(parent)
        self.layer_name = layer_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.name_label = QLabel(display_name)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.name_label)

        self.status_badge = QLabel("None")
        self.status_badge.setFixedWidth(80)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet(self._badge_style("#8A93A3"))
        layout.addWidget(self.status_badge)

        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.setFixedHeight(26)
        self.confirm_button.setFixedWidth(70)
        self.confirm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.confirm_button.clicked.connect(lambda: self.confirmRequested.emit(self.layer_name))
        layout.addWidget(self.confirm_button)

    @staticmethod
    def _badge_style(color):
        return (
            f"background-color: {color}; color: #14151A; border-radius: 6px; "
            f"font-weight: bold; padding: 2px 6px;"
        )

    def set_status(self, status: str):
        label, color = STATUS_INFO.get(status, STATUS_INFO["none"])
        self.status_badge.setText(label)
        self.status_badge.setStyleSheet(self._badge_style(color))
        self.confirm_button.setEnabled(status != "confirmed")


class AnnotationStatusPanel(QWidget):
    """
    Per-layer annotation status for the CURRENT frame — replaces the old
    single-layer ConfirmationBar that sat above the graphics view. Shows
    all four layers at once, each with its own Confirm button, since a
    single frame can be at a different review stage per layer.
    """
    confirmRequested = pyqtSignal(str)  # layer_name

    LAYER_DISPLAY = {"ball": "Ball", "players": "Players", "actions": "Actions", "court": "Court"}
    LAYER_ORDER = ["ball", "players", "actions", "court"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)

        for layer_name in self.LAYER_ORDER:
            row = AnnotationStatusRow(layer_name, self.LAYER_DISPLAY.get(layer_name, layer_name))
            row.confirmRequested.connect(self.confirmRequested.emit)
            self.rows[layer_name] = row
            layout.addWidget(row)

    def set_statuses(self, statuses: dict):
        for layer_name, row in self.rows.items():
            row.set_status(statuses.get(layer_name, "none"))


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
    setPathRequested = pyqtSignal(str)
    gameStateDetectRequested = pyqtSignal()
    confirmLayerRequested = pyqtSignal(str)

    def __init__(self, model_status=None, model_paths=None, parent=None):
        super().__init__(parent)
        self.model_status = model_status or {}
        self.model_paths = model_paths or {}  # NEW

        self.setObjectName("rightSidebar")
        self.setFixedWidth(340)  # widened from 300 to fit the inline path button

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
            "Auto-Annotation",
            "./resources/icons/right_sidebar/AI.png",
            self,
        )

        main_layout.addWidget(header)

        # -----------------------------------------------------
        # Detection section
        # -----------------------------------------------------

        section_title = QLabel("Object Detection")
        section_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        main_layout.addWidget(section_title)

        self.ball_row = DetectionRow(
            "ball",
            "Ball",
            "./resources/icons/right_sidebar/ball.png",
            icon_size=30,
            model_path=self.model_paths.get("ball"),
            parent=self,
        )
        self.players_row = DetectionRow(
            "players",
            "Players",
            "./resources/icons/right_sidebar/players.png",
            icon_size=30,
            model_path=self.model_paths.get("players"),
            parent=self
        )
        self.actions_row = DetectionRow(
            "actions",
            "Actions",
            "./resources/icons/right_sidebar/actions.png",
            icon_size=30,
            model_path=self.model_paths.get("actions"),
            parent=self,
        )

        self.ball_row.clicked.connect(lambda: self.detectRequested.emit("ball"))
        self.players_row.clicked.connect(lambda: self.detectRequested.emit("players"))
        self.actions_row.clicked.connect(lambda: self.detectRequested.emit("actions"))

        self.ball_row.pathRequested.connect(lambda: self.setPathRequested.emit("ball"))
        self.players_row.pathRequested.connect(lambda: self.setPathRequested.emit("players"))
        self.actions_row.pathRequested.connect(lambda: self.setPathRequested.emit("actions"))

        main_layout.addWidget(self.ball_row)
        main_layout.addWidget(self.players_row)
        main_layout.addWidget(self.actions_row)

        # -----------------------------------------------------
        # Separator
        # -----------------------------------------------------

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(separator)

        # ----------------------------------------------------
        # Game State Section
        # ----------------------------------------------------

        section_title2 = QLabel("Game State (Video)")
        section_title2.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        main_layout.addWidget(section_title2)

        self.game_state_row = GameStateRow(
            "./resources/icons/right_sidebar/clapperboard.png",  # swap in a dedicated icon when you have one
            icon_size=30,
            model_path=self.model_paths.get("game_state"),
            parent=self,
        )

        self.game_state_row.runRequested.connect(self.gameStateDetectRequested.emit)
        self.game_state_row.pathRequested.connect(lambda: self.setPathRequested.emit("game_state"))
        main_layout.addWidget(self.game_state_row)

        # -----------------------------------------------------
        # Separator
        # -----------------------------------------------------

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(separator)

        # -----------------------------------------------------
        # Separator
        # -----------------------------------------------------

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(separator)

        # -----------------------------------------------------
        # Configure Job
        # -----------------------------------------------------

        self.configure_button = QPushButton("Quick Annotate")
        self.configure_button.setIcon(QIcon("./resources/icons/right_sidebar/thunder.png"))
        self.configure_button.setIconSize(QSize(25, 25))
        self.configure_button.setFixedHeight(38)
        self.configure_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.configure_button.clicked.connect(self.configureJobRequested.emit)
        main_layout.addWidget(self.configure_button)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(separator)

        section_title3 = QLabel("Annotation Status")
        section_title3.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        main_layout.addWidget(section_title3)

        self.annotation_status_panel = AnnotationStatusPanel(parent=self)
        self.annotation_status_panel.confirmRequested.connect(self.confirmLayerRequested.emit)
        main_layout.addWidget(self.annotation_status_panel)

        # Push everything to the top
        main_layout.addStretch()

    # ---------------------------------------------------------
    # Model status
    # ---------------------------------------------------------
    def set_model_status(self, model_name, configured, model_path=None):
        if model_name == "ball":
            self.ball_row.update_status(configured, model_path)
        elif model_name == "players":
            self.players_row.update_status(configured, model_path)
        elif model_name == "actions":
            self.actions_row.update_status(configured, model_path)
        elif model_name == "game_state":
            self.game_state_row.update_status(configured, model_path)

    def set_annotation_statuses(self, statuses):
        self.annotation_status_panel.set_statuses(statuses)

    def refresh_status(self):
        self.set_model_status(
            "ball",
            self.model_status.get("ball", False),
            self.model_paths.get("ball")
        )
        self.set_model_status(
            "players",
            self.model_status.get("players", False),
            self.model_paths.get("players")
        )
        self.set_model_status(
            "actions",
            self.model_status.get("actions", False),
            self.model_paths.get("actions")
        )
        self.set_model_status(
            "game_state",
            self.model_status.get("game_state", False),
            self.model_paths.get("game_state")
        )
