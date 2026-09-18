from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vb_gui.vb_annotator.database.database_cleanup_manager import DatabaseCleanupManager, DatabaseDeleteFilter


class DatabaseManagementDialog(QDialog):
    """
    UI for selectively removing annotation/game-state data from the
    application database.

    Exactly one video can be selected.
    """

    LAYERS = (
        ("actions", "Actions"),
        ("players", "Players"),
        ("ball", "Ball"),
        ("court", "Court"),
        ("game-state", "Game State"),
    )

    def __init__(
            self,
            db_path: str = "annotations.db",
            parent=None,
    ):
        super().__init__(parent)

        self.manager = DatabaseCleanupManager(db_path)

        self.setWindowTitle("Database Management")
        self.setMinimumSize(760, 680)
        self.resize(820, 720)

        self._build_ui()
        self._load_videos()
        self._connect_signals()

        self._update_range_state()
        self._update_game_state_state()
        self._update_preview()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Database Management")
        title.setObjectName("databaseTitle")
        root.addWidget(title)

        description = QLabel(
            "Select one video and choose exactly which database records "
            "you want to remove."
        )
        description.setWordWrap(True)
        description.setObjectName("databaseDescription")
        root.addWidget(description)

        # --------------------------------------------------------------
        # Video
        # --------------------------------------------------------------

        video_group = QGroupBox("Video")
        video_layout = QVBoxLayout(video_group)

        self.video_combo = QComboBox()
        self.video_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        video_layout.addWidget(self.video_combo)

        self.video_info_label = QLabel("No video selected.")
        self.video_info_label.setObjectName("databaseInfo")
        video_layout.addWidget(self.video_info_label)

        root.addWidget(video_group)

        # --------------------------------------------------------------
        # Frame range
        # --------------------------------------------------------------

        range_group = QGroupBox("Frame Range")
        range_layout = QVBoxLayout(range_group)

        self.all_frames_checkbox = QCheckBox("All frames")
        self.all_frames_checkbox.setChecked(True)

        range_layout.addWidget(self.all_frames_checkbox)

        frame_grid = QGridLayout()

        frame_grid.addWidget(
            QLabel("Start frame"),
            0,
            0,
        )

        self.start_frame_spin = QSpinBox()
        self.start_frame_spin.setMinimum(0)
        self.start_frame_spin.setMaximum(0)
        self.start_frame_spin.setEnabled(False)

        frame_grid.addWidget(
            self.start_frame_spin,
            0,
            1,
        )

        frame_grid.addWidget(
            QLabel("End frame"),
            0,
            2,
        )

        self.end_frame_spin = QSpinBox()
        self.end_frame_spin.setMinimum(0)
        self.end_frame_spin.setMaximum(0)
        self.end_frame_spin.setEnabled(False)

        frame_grid.addWidget(
            self.end_frame_spin,
            0,
            3,
        )

        range_layout.addLayout(frame_grid)

        # Visual range indicator.
        self.range_indicator = QFrame()
        self.range_indicator.setObjectName("frameRangeIndicator")
        self.range_indicator.setMinimumHeight(12)
        self.range_indicator.setMaximumHeight(12)

        range_layout.addWidget(self.range_indicator)

        self.range_info_label = QLabel()
        self.range_info_label.setObjectName("databaseInfo")
        range_layout.addWidget(self.range_info_label)

        root.addWidget(range_group)

        # --------------------------------------------------------------
        # Content
        # --------------------------------------------------------------

        content_group = QGroupBox("Content to Remove")
        content_layout = QGridLayout(content_group)

        self.layer_checkboxes = {}

        for index, (key, label) in enumerate(self.LAYERS):
            checkbox = QCheckBox(label)
            checkbox.setChecked(False)

            self.layer_checkboxes[key] = checkbox

            row = index // 3
            column = index % 3

            content_layout.addWidget(
                checkbox,
                row,
                column,
            )

        root.addWidget(content_group)

        # --------------------------------------------------------------
        # Annotation origin
        # --------------------------------------------------------------

        origin_group = QGroupBox("Annotation Origin")
        origin_layout = QHBoxLayout(origin_group)

        self.ai_checkbox = QCheckBox("AI-generated")
        self.ai_checkbox.setChecked(True)

        self.human_checkbox = QCheckBox("Human")
        self.human_checkbox.setChecked(True)

        origin_layout.addWidget(self.ai_checkbox)
        origin_layout.addWidget(self.human_checkbox)
        origin_layout.addStretch()

        root.addWidget(origin_group)

        # --------------------------------------------------------------
        # Annotation review status
        # --------------------------------------------------------------

        status_group = QGroupBox("Annotation Review Status")
        status_layout = QHBoxLayout(status_group)

        self.confirmed_checkbox = QCheckBox("Confirmed")
        self.confirmed_checkbox.setChecked(True)

        self.unconfirmed_checkbox = QCheckBox("Unconfirmed")
        self.unconfirmed_checkbox.setChecked(True)

        status_layout.addWidget(self.confirmed_checkbox)
        status_layout.addWidget(self.unconfirmed_checkbox)
        status_layout.addStretch()

        root.addWidget(status_group)

        # --------------------------------------------------------------
        # Game state source
        # --------------------------------------------------------------

        self.game_state_source_group = QGroupBox(
            "Game-State Source"
        )

        source_layout = QHBoxLayout(
            self.game_state_source_group
        )

        self.model_source_checkbox = QCheckBox("Model")
        self.model_source_checkbox.setChecked(True)

        self.manual_source_checkbox = QCheckBox("Manual")
        self.manual_source_checkbox.setChecked(True)

        source_layout.addWidget(self.model_source_checkbox)
        source_layout.addWidget(self.manual_source_checkbox)
        source_layout.addStretch()

        root.addWidget(self.game_state_source_group)

        # --------------------------------------------------------------
        # Preview
        # --------------------------------------------------------------

        preview_group = QGroupBox("Deletion Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel(
            "Select content to see what will be removed."
        )
        self.preview_label.setWordWrap(True)

        preview_layout.addWidget(self.preview_label)

        root.addWidget(preview_group)

        root.addStretch()

        # --------------------------------------------------------------
        # Buttons
        # --------------------------------------------------------------

        buttons_layout = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._load_videos)

        buttons_layout.addWidget(self.refresh_button)

        buttons_layout.addStretch()

        self.cancel_button = QPushButton("Close")
        self.cancel_button.clicked.connect(self.reject)

        self.delete_button = QPushButton(
            "Delete Selected Data"
        )
        self.delete_button.setObjectName(
            "dangerButton"
        )

        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addWidget(self.delete_button)

        root.addLayout(buttons_layout)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.video_combo.currentIndexChanged.connect(
            self._on_video_changed
        )

        self.all_frames_checkbox.toggled.connect(
            self._update_range_state
        )

        self.start_frame_spin.valueChanged.connect(
            self._on_start_frame_changed
        )

        self.end_frame_spin.valueChanged.connect(
            self._on_end_frame_changed
        )

        for checkbox in self.layer_checkboxes.values():
            checkbox.toggled.connect(
                self._on_filter_changed
            )

        self.ai_checkbox.toggled.connect(
            self._on_filter_changed
        )

        self.human_checkbox.toggled.connect(
            self._on_filter_changed
        )

        self.confirmed_checkbox.toggled.connect(
            self._on_filter_changed
        )

        self.unconfirmed_checkbox.toggled.connect(
            self._on_filter_changed
        )

        self.model_source_checkbox.toggled.connect(
            self._on_filter_changed
        )

        self.manual_source_checkbox.toggled.connect(
            self._on_filter_changed
        )

        self.delete_button.clicked.connect(
            self._delete_selected_data
        )

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------

    def _load_videos(self):
        current_path = self._selected_video_path()

        self.video_combo.blockSignals(True)
        self.video_combo.clear()

        videos = self.manager.get_videos()

        for video in videos:
            self.video_combo.addItem(
                video.path,
                userData=video.path,
            )

        self.video_combo.blockSignals(False)

        if current_path:
            index = self.video_combo.findData(
                current_path
            )

            if index >= 0:
                self.video_combo.setCurrentIndex(index)

        if self.video_combo.count() > 0:
            self._on_video_changed(
                self.video_combo.currentIndex()
            )
        else:
            self.video_info_label.setText(
                "No videos are registered in the database."
            )
            self.delete_button.setEnabled(False)

        self._update_preview()

    def _selected_video_path(self):
        return self.video_combo.currentData()

    def _on_video_changed(self, index):
        path = self._selected_video_path()

        if not path:
            self.delete_button.setEnabled(False)
            self.video_info_label.setText(
                "No video selected."
            )
            return

        media = self.manager.get_media(path)

        if media is None:
            self.delete_button.setEnabled(False)
            return

        max_frame = self.manager.get_video_frame_count(
            path
        )

        self.start_frame_spin.setMaximum(
            max_frame
        )

        self.end_frame_spin.setMaximum(
            max_frame
        )

        self.start_frame_spin.setValue(0)
        self.end_frame_spin.setValue(max_frame)

        self.video_info_label.setText(
            f"{media.path}    "
            f"({media.width} × {media.height})    "
            f"up to frame {max_frame}"
        )

        self.delete_button.setEnabled(True)

        self._update_preview()

    # ------------------------------------------------------------------
    # Frame range
    # ------------------------------------------------------------------

    def _update_range_state(self):
        enabled = not self.all_frames_checkbox.isChecked()

        self.start_frame_spin.setEnabled(enabled)
        self.end_frame_spin.setEnabled(enabled)

        if enabled:
            self.range_info_label.setText(
                f"Selected range: "
                f"{self.start_frame_spin.value()} → "
                f"{self.end_frame_spin.value()}"
            )
        else:
            self.range_info_label.setText(
                "All frames of the selected video"
            )

        self._update_preview()

    def _on_start_frame_changed(self, value):
        if value > self.end_frame_spin.value():
            self.end_frame_spin.setValue(value)

        self._update_range_state()

    def _on_end_frame_changed(self, value):
        if value < self.start_frame_spin.value():
            self.start_frame_spin.setValue(value)

        self._update_range_state()

    # ------------------------------------------------------------------
    # Filter changes
    # ------------------------------------------------------------------

    def _on_filter_changed(self):
        self._update_game_state_state()
        self._update_preview()

    def _update_game_state_state(self):
        game_state_selected = self.layer_checkboxes[
            "game-state"
        ].isChecked()

        self.game_state_source_group.setEnabled(
            game_state_selected
        )

    # ------------------------------------------------------------------
    # Build filter
    # ------------------------------------------------------------------

    def _build_filter(self):
        layers = [
            key
            for key, checkbox
            in self.layer_checkboxes.items()
            if checkbox.isChecked()
        ]

        annotation_origins = []

        if self.ai_checkbox.isChecked():
            annotation_origins.append("ai")

        if self.human_checkbox.isChecked():
            annotation_origins.append("human")

        annotation_statuses = []

        if self.confirmed_checkbox.isChecked():
            annotation_statuses.append("confirmed")

        if self.unconfirmed_checkbox.isChecked():
            annotation_statuses.append("unconfirmed")

        game_state_sources = []

        if self.model_source_checkbox.isChecked():
            game_state_sources.append("model")

        if self.manual_source_checkbox.isChecked():
            game_state_sources.append("manual")

        return DatabaseDeleteFilter(
            media_path=self._selected_video_path(),
            start_frame=self.start_frame_spin.value(),
            end_frame=self.end_frame_spin.value(),
            delete_all_frames=self.all_frames_checkbox.isChecked(),
            layers=layers,
            annotation_origins=annotation_origins,
            annotation_statuses=annotation_statuses,
            game_state_sources=game_state_sources,
        )

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _update_preview(self):
        path = self._selected_video_path()

        if not path:
            self.preview_label.setText(
                "No video selected."
            )
            return

        delete_filter = self._build_filter()

        preview = self.manager.preview_delete(
            delete_filter
        )

        self.preview_label.setText(
            f"Annotations: {preview.annotation_count:,}\n"
            f"Game-state segments: "
            f"{preview.game_state_segment_count:,}\n"
            f"Total database records affected: "
            f"{preview.total:,}"
        )

        self.delete_button.setEnabled(
            bool(path) and preview.total > 0
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _delete_selected_data(self):
        path = self._selected_video_path()

        if not path:
            return

        delete_filter = self._build_filter()

        preview = self.manager.preview_delete(
            delete_filter
        )

        if preview.total == 0:
            QMessageBox.information(
                self,
                "Nothing to Delete",
                "No database records match the selected filters.",
            )
            return

        # --------------------------------------------------------------
        # Confirmation
        # --------------------------------------------------------------

        if delete_filter.delete_all_frames:
            frame_description = "ALL frames"
        else:
            frame_description = (
                f"frames "
                f"{delete_filter.start_frame:,} → "
                f"{delete_filter.end_frame:,}"
            )

        selected_content = [
            label
            for key, label in self.LAYERS
            if key in delete_filter.layers
        ]

        message = (
            "The following database records will be permanently deleted:\n\n"
            f"Video:\n{path}\n\n"
            f"Frames:\n{frame_description}\n\n"
            f"Content:\n"
            f"{', '.join(selected_content) or 'None'}\n\n"
            f"Annotations: {preview.annotation_count:,}\n"
            f"Game-state segments affected: "
            f"{preview.game_state_segment_count:,}\n\n"
            "This operation cannot be undone.\n\n"
            "Continue?"
        )

        answer = QMessageBox.warning(
            self,
            "Confirm Database Deletion",
            message,
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        # --------------------------------------------------------------
        # Execute
        # --------------------------------------------------------------

        try:
            result = self.manager.delete(
                delete_filter
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Database Error",
                f"Could not delete the selected data:\n\n{exc}",
            )
            return

        QMessageBox.information(
            self,
            "Database Updated",
            (
                "Database cleanup completed.\n\n"
                f"Annotations removed: "
                f"{result.annotation_count:,}\n"
                f"Game-state segments affected: "
                f"{result.game_state_segment_count:,}\n"
                f"Total records affected: "
                f"{result.total:,}"
            ),
        )

        self._load_videos()
        self._update_preview()
