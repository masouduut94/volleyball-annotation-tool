from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
                             QCheckBox, QPushButton, QFileDialog, QListWidget,
                             QListWidgetItem, QFrame, QSpinBox, QMessageBox)


class VideoMAEExportDialog(QDialog):
    """
    Dialog for building a frame-clip dataset for the VideoMAE game-state
    classifier out of stored game_state_segments.
    """

    AUGMENTATIONS = [
        ("brightness_contrast", "Random Brightness / Contrast"),
        ("horizontal_flip", "Flip Left / Right"),
        ("rgb_manipulation", "RGB Manipulation (color shift)"),
    ]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Export VideoMAE Dataset")
        self.resize(650, 650)

        self._create_ui()
        self._load_videos()

    # ==========================================================
    # UI
    # ==========================================================

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ------------------------------------------------------
        # Videos
        # ------------------------------------------------------

        videos_group = QGroupBox("Videos")
        videos_layout = QVBoxLayout(videos_group)

        self.video_list = QListWidget()
        videos_layout.addWidget(self.video_list)

        video_buttons = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._set_all_videos(True))
        deselect_all = QPushButton("Deselect All")
        deselect_all.clicked.connect(lambda: self._set_all_videos(False))
        video_buttons.addWidget(select_all)
        video_buttons.addWidget(deselect_all)
        video_buttons.addStretch()
        videos_layout.addLayout(video_buttons)

        layout.addWidget(videos_group)

        # ------------------------------------------------------
        # Clip settings
        # ------------------------------------------------------

        clip_group = QGroupBox("Clip Settings")
        clip_layout = QVBoxLayout(clip_group)

        length_row = QHBoxLayout()
        length_row.addWidget(QLabel("Frames per clip:"))
        self.clip_length_spin = QSpinBox()
        self.clip_length_spin.setRange(4, 300)
        self.clip_length_spin.setValue(16)
        length_row.addWidget(self.clip_length_spin)
        length_row.addStretch()
        clip_layout.addLayout(length_row)

        service_note = QLabel(
            "Service: uses every recorded 'service' segment as one clip each "
            "— service periods are short and scarce, so none are skipped."
        )
        service_note.setWordWrap(True)
        service_note.setStyleSheet("color: #9096A3; font-size: 11px;")
        clip_layout.addWidget(service_note)

        random_note = QLabel(
            "In-Play / No-Play: random windows are drawn from anywhere inside "
            "the recorded segments (longer segments contribute more candidate "
            "windows) until the requested clip count below is reached."
        )
        random_note.setWordWrap(True)
        random_note.setStyleSheet("color: #9096A3; font-size: 11px;")
        clip_layout.addWidget(random_note)

        counts_row = QHBoxLayout()
        counts_row.addWidget(QLabel("In-Play clips:"))
        self.play_count_spin = QSpinBox()
        self.play_count_spin.setRange(0, 100000)
        self.play_count_spin.setValue(100)
        counts_row.addWidget(self.play_count_spin)

        counts_row.addSpacing(16)
        counts_row.addWidget(QLabel("No-Play clips:"))
        self.no_play_count_spin = QSpinBox()
        self.no_play_count_spin.setRange(0, 100000)
        self.no_play_count_spin.setValue(100)
        counts_row.addWidget(self.no_play_count_spin)
        counts_row.addStretch()
        clip_layout.addLayout(counts_row)

        layout.addWidget(clip_group)

        # ------------------------------------------------------
        # Augmentation
        # ------------------------------------------------------

        aug_group = QGroupBox("Augmentation")
        aug_layout = QVBoxLayout(aug_group)

        self.aug_checkboxes = {}
        for key, display in self.AUGMENTATIONS:
            checkbox = QCheckBox(display)
            checkbox.setChecked(False)
            self.aug_checkboxes[key] = checkbox
            aug_layout.addWidget(checkbox)

        aug_hint = QLabel(
            "Each enabled augmentation adds one extra copy of every clip, "
            "consistently applied across all frames of that clip."
        )
        aug_hint.setWordWrap(True)
        aug_hint.setStyleSheet("color: #9096A3; font-size: 11px;")
        aug_layout.addWidget(aug_hint)

        layout.addWidget(aug_group)

        # ------------------------------------------------------
        # Output directory
        # ------------------------------------------------------

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output:"))
        self.output_edit = QLabel("No output directory selected")
        self.output_edit.setFrameStyle(QFrame.Shape.StyledPanel)
        self.output_edit.setWordWrap(True)
        output_layout.addWidget(self.output_edit, stretch=1)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._choose_output_directory)
        output_layout.addWidget(browse_button)
        layout.addLayout(output_layout)

        # ------------------------------------------------------
        # Buttons
        # ------------------------------------------------------

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        export_button = QPushButton("Export")
        export_button.setDefault(True)
        export_button.clicked.connect(self._export)
        buttons.addWidget(cancel_button)
        buttons.addWidget(export_button)
        layout.addLayout(buttons)

    # ==========================================================
    # Videos
    # ==========================================================

    def _load_videos(self):
        self.video_list.clear()
        for media in self.db.get_all_media():
            if media.media_type != "video":
                continue
            segments = self.db.get_game_state_segments(media.path)
            if not segments:
                continue  # nothing to build clips from

            item = QListWidgetItem(Path(media.path).name)
            item.setToolTip(media.path)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, media.path)
            self.video_list.addItem(item)

    def _set_all_videos(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.video_list.count()):
            self.video_list.item(i).setCheckState(state)

    # ==========================================================
    # Output
    # ==========================================================

    def _choose_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_edit.setText(directory)

    # ==========================================================
    # Export
    # ==========================================================

    def _collect_settings(self):
        selected_videos = []
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_videos.append(item.data(Qt.ItemDataRole.UserRole))

        output_dir = self.output_edit.text()
        if output_dir == "No output directory selected":
            output_dir = ""

        augmentations = [key for key, cb in self.aug_checkboxes.items() if cb.isChecked()]

        return {
            "videos": selected_videos,
            "clip_length": self.clip_length_spin.value(),
            "play_clip_count": self.play_count_spin.value(),
            "no_play_clip_count": self.no_play_count_spin.value(),
            "augmentations": augmentations,
            "output_dir": output_dir,
        }

    def _export(self):
        settings = self._collect_settings()

        if not settings["output_dir"]:
            QMessageBox.warning(self, "Output Directory", "Please select an output directory.")
            return

        if not settings["videos"]:
            QMessageBox.warning(self, "Videos", "Please select at least one video.")
            return

        if settings["play_clip_count"] == 0 and settings["no_play_clip_count"] == 0:
            reply = QMessageBox.question(
                self, "No Random Clips Requested",
                "In-Play and No-Play clip counts are both 0 — only Service "
                "clips will be exported. Continue anyway?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.export_settings = settings
        self.accept()

    def get_settings(self):
        return getattr(self, "export_settings", None)