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


from PyQt6.QtWidgets import QComboBox, QSpinBox, QGridLayout, QFrame  # add to your imports


class TagRow(QWidget):
    """
    Manual ground-truth tagging tool for game-state segments.

    Two mutually exclusive modes, decided by MainWindow based on the
    current frame:
      - CREATE: no segment covers the current frame. "Mark Start" ->
        "Mark End" flow, same as before. Nothing is saved until both
        ends are marked.
      - EDIT: the current frame falls inside an existing segment. Shows
        its start/end/label, editable, plus Apply and Delete.

    A pending create always takes priority over showing the edit panel,
    since you're mid-way through defining a new tag.
    """
    markStartRequested = pyqtSignal(str)
    markEndRequested = pyqtSignal()
    cancelRequested = pyqtSignal()

    editApplyRequested = pyqtSignal(int, int, str)   # start, end, state
    editDeleteRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending = False
        self._editing_segment = None
        self._max_frame = 10 ** 7
        self._setup_ui()
        self._refresh_visibility()

    def _setup_ui(self):
        self.setObjectName("detectionRow")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        name_label = QLabel("Tag")
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_row.addWidget(name_label)
        layout.addLayout(title_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("tagStatusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # ---------------------------------------------------------
        # CREATE panel
        # ---------------------------------------------------------
        self.create_panel = QWidget()
        create_layout = QHBoxLayout(self.create_panel)
        create_layout.setContentsMargins(0, 0, 0, 0)
        create_layout.setSpacing(8)

        self.state_combo = QComboBox()
        self.state_combo.addItems(["service", "play", "no-play"])
        self.state_combo.setFixedWidth(100)
        create_layout.addWidget(self.state_combo)

        self.action_button = QPushButton("Mark Start")
        self.action_button.setFixedHeight(28)
        self.action_button.clicked.connect(self._on_action_clicked)
        create_layout.addWidget(self.action_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(28)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        create_layout.addWidget(self.cancel_button)

        layout.addWidget(self.create_panel)

        # ---------------------------------------------------------
        # EDIT panel — shown when the current frame is inside a segment
        # ---------------------------------------------------------
        self.edit_panel = QWidget()
        edit_layout = QVBoxLayout(self.edit_panel)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)

        grid.addWidget(QLabel("Label"), 0, 0)
        self.edit_state_combo = QComboBox()
        self.edit_state_combo.addItems(["service", "play", "no-play"])
        grid.addWidget(self.edit_state_combo, 0, 1, 1, 2)

        grid.addWidget(QLabel("Start"), 1, 0)
        self.edit_start_spin = QSpinBox()
        self.edit_start_spin.setRange(0, self._max_frame)
        grid.addWidget(self.edit_start_spin, 1, 1)
        self.edit_start_use_current = QPushButton("Use current")
        self.edit_start_use_current.setFixedHeight(24)
        grid.addWidget(self.edit_start_use_current, 1, 2)

        grid.addWidget(QLabel("End"), 2, 0)
        self.edit_end_spin = QSpinBox()
        self.edit_end_spin.setRange(0, self._max_frame)
        grid.addWidget(self.edit_end_spin, 2, 1)
        self.edit_end_use_current = QPushButton("Use current")
        self.edit_end_use_current.setFixedHeight(24)
        grid.addWidget(self.edit_end_use_current, 2, 2)

        edit_layout.addLayout(grid)

        edit_btn_row = QHBoxLayout()
        self.edit_apply_button = QPushButton("Apply Changes")
        self.edit_apply_button.setFixedHeight(28)
        self.edit_apply_button.clicked.connect(self._on_apply_clicked)
        edit_btn_row.addWidget(self.edit_apply_button)

        self.edit_delete_button = QPushButton("Delete Tag")
        self.edit_delete_button.setFixedHeight(28)
        self.edit_delete_button.setObjectName("dangerButton")
        self.edit_delete_button.clicked.connect(self.editDeleteRequested.emit)
        edit_btn_row.addWidget(self.edit_delete_button)

        edit_layout.addLayout(edit_btn_row)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        edit_layout.insertWidget(0, separator)

        layout.addWidget(self.edit_panel)

        # "Use current" buttons need to know the live frame number, but
        # this widget has no navigation state of its own — MainWindow
        # supplies it via set_current_frame().
        self._current_frame = 0
        self.edit_start_use_current.clicked.connect(
            lambda: self.edit_start_spin.setValue(self._current_frame)
        )
        self.edit_end_use_current.clicked.connect(
            lambda: self.edit_end_spin.setValue(self._current_frame)
        )

    # ---------------------------------------------------------
    # Create-flow handlers
    # ---------------------------------------------------------

    def _on_action_clicked(self):
        if self._pending:
            self.markEndRequested.emit()
        else:
            self.markStartRequested.emit(self.state_combo.currentText())

    def set_pending(self, pending: bool, start_frame=None, state=None):
        self._pending = pending
        if pending:
            self.action_button.setText("Mark End")
            self.cancel_button.setVisible(True)
            self.state_combo.setEnabled(False)
            self.status_label.setText(
                f"Marking '{state}' — start at frame {start_frame}. "
                f"Move to the end frame and click Mark End."
            )
        else:
            self.action_button.setText("Mark Start")
            self.cancel_button.setVisible(False)
            self.state_combo.setEnabled(True)
            self.status_label.setText("")
        self._refresh_visibility()

    # ---------------------------------------------------------
    # Edit-flow handlers
    # ---------------------------------------------------------

    def _on_apply_clicked(self):
        self.editApplyRequested.emit(
            self.edit_start_spin.value(),
            self.edit_end_spin.value(),
            self.edit_state_combo.currentText(),
        )

    def set_editing(self, segment):
        """segment: a GameStateSegment dataclass, or None."""
        self._editing_segment = segment
        if segment is not None:
            self.edit_state_combo.setCurrentText(segment.state)
            self.edit_start_spin.setValue(segment.start_frame)
            self.edit_end_spin.setValue(segment.end_frame)
            src_label = "manual" if segment.source == "manual" else "AI-generated"
            self.status_label.setText(
                f"Editing existing tag ({src_label}), frames "
                f"{segment.start_frame}\u2013{segment.end_frame}."
            )
        self._refresh_visibility()

    def set_current_frame(self, frame_number: int):
        self._current_frame = frame_number

    def set_max_frame(self, max_frame: int):
        self._max_frame = max(0, max_frame)
        self.edit_start_spin.setRange(0, self._max_frame)
        self.edit_end_spin.setRange(0, self._max_frame)

    # ---------------------------------------------------------
    # Visibility
    # ---------------------------------------------------------

    def _refresh_visibility(self):
        editing = (not self._pending) and (self._editing_segment is not None)
        self.create_panel.setVisible(not editing)
        self.edit_panel.setVisible(editing)
        if not self._pending and self._editing_segment is None:
            self.status_label.setText("")


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

    tagMarkStartRequested = pyqtSignal(str)
    tagMarkEndRequested = pyqtSignal()
    tagCancelRequested = pyqtSignal()
    tagEditApplyRequested = pyqtSignal(int, int, str)
    tagEditDeleteRequested = pyqtSignal()

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

        self.tag_row = TagRow(parent=self)
        self.tag_row.markStartRequested.connect(self.tagMarkStartRequested.emit)
        self.tag_row.markEndRequested.connect(self.tagMarkEndRequested.emit)
        self.tag_row.cancelRequested.connect(self.tagCancelRequested.emit)
        self.tag_row.editApplyRequested.connect(self.tagEditApplyRequested.emit)
        self.tag_row.editDeleteRequested.connect(self.tagEditDeleteRequested.emit)
        main_layout.addWidget(self.tag_row)


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
        # Push everything to the top
        main_layout.addStretch()

    # ---------------------------------------------------------
    # Model status
    # ---------------------------------------------------------

    def set_tag_editing(self, segment):
        self.tag_row.set_editing(segment)

    def set_tag_current_frame(self, frame_number):
        self.tag_row.set_current_frame(frame_number)

    def set_tag_max_frame(self, max_frame):
        self.tag_row.set_max_frame(max_frame)

    def set_tag_pending(self, pending, start_frame=None, state=None):
        self.tag_row.set_pending(pending, start_frame, state)

    def set_model_status(self, model_name, configured, model_path=None):
        if model_name == "ball":
            self.ball_row.update_status(configured, model_path)
        elif model_name == "players":
            self.players_row.update_status(configured, model_path)
        elif model_name == "actions":
            self.actions_row.update_status(configured, model_path)
        elif model_name == "game_state":
            self.game_state_row.update_status(configured, model_path)

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
