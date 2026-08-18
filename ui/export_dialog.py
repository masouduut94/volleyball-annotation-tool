from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QCheckBox,
    QPushButton,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QSpinBox,
    QMessageBox,
)


class YOLOExportDialog(QDialog):
    """
    Dialog for configuring YOLO dataset export.
    """

    LAYERS = [
        "court",
        "players",
        "ball",
        "actions",
    ]

    def __init__(self, db, parent=None):
        super().__init__(parent)

        self.db = db

        self.setWindowTitle("Export YOLO Dataset")
        self.resize(850, 800)

        self.layer_checkboxes = {}
        self.label_checkboxes = {}

        self._create_ui()
        self._load_layers()
        self._load_videos()

    # ==========================================================
    # UI
    # ==========================================================

    def _create_ui(self):

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ======================================================
        # Export mode + annotation format
        # ======================================================

        top_group = QGroupBox()

        top_layout = QHBoxLayout(top_group)

        # ------------------------------------------------------
        # Export mode
        # ------------------------------------------------------

        mode_group = QGroupBox("Export Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.combined_radio = QRadioButton(
            "Combined dataset"
        )

        self.separate_radio = QRadioButton(
            "Separate datasets"
        )

        self.combined_radio.setChecked(True)

        mode_layout.addWidget(
            self.combined_radio
        )
        mode_layout.addWidget(
            self.separate_radio
        )

        # ------------------------------------------------------
        # Annotation format
        # ------------------------------------------------------

        format_group = QGroupBox(
            "Annotation Format"
        )

        format_layout = QVBoxLayout(
            format_group
        )

        self.detection_radio = QRadioButton(
            "YOLO Detection (Bounding Boxes)"
        )

        self.segmentation_radio = QRadioButton(
            "YOLO Segmentation (Polygons)"
        )

        self.detection_radio.setChecked(True)

        format_layout.addWidget(
            self.detection_radio
        )
        format_layout.addWidget(
            self.segmentation_radio
        )

        top_layout.addWidget(
            mode_group,
            stretch=1
        )

        top_layout.addWidget(
            format_group,
            stretch=1
        )

        layout.addWidget(top_group)

        # ======================================================
        # Layers + Labels
        # ======================================================

        selection_group = QGroupBox(
            "Layers and Labels"
        )

        selection_layout = QHBoxLayout(
            selection_group
        )

        # ------------------------------------------------------
        # Layers
        # ------------------------------------------------------

        layers_group = QGroupBox("Layers")
        layers_layout = QVBoxLayout(
            layers_group
        )

        for layer_name in self.LAYERS:

            checkbox = QCheckBox(
                layer_name.capitalize()
            )

            checkbox.setChecked(True)

            checkbox.stateChanged.connect(
                self._layers_changed
            )

            self.layer_checkboxes[
                layer_name
            ] = checkbox

            layers_layout.addWidget(
                checkbox
            )

        layers_layout.addStretch()

        # ------------------------------------------------------
        # Labels
        # ------------------------------------------------------

        labels_group = QGroupBox("Labels")
        self.labels_layout = QGridLayout(
            labels_group
        )

        selection_layout.addWidget(
            layers_group,
            stretch=1
        )

        selection_layout.addWidget(
            labels_group,
            stretch=3
        )

        self.labels_group = labels_group

        layout.addWidget(
            selection_group
        )

        # ======================================================
        # Videos
        # ======================================================

        videos_group = QGroupBox(
            "Videos / Media"
        )

        videos_layout = QVBoxLayout(
            videos_group
        )

        self.video_list = QListWidget()

        videos_layout.addWidget(
            self.video_list
        )

        video_buttons = QHBoxLayout()

        select_all_videos = QPushButton(
            "Select All"
        )

        select_all_videos.clicked.connect(
            lambda: self._set_all_videos(True)
        )

        deselect_all_videos = QPushButton(
            "Deselect All"
        )

        deselect_all_videos.clicked.connect(
            lambda: self._set_all_videos(False)
        )

        video_buttons.addWidget(
            select_all_videos
        )

        video_buttons.addWidget(
            deselect_all_videos
        )

        video_buttons.addStretch()

        videos_layout.addLayout(
            video_buttons
        )

        layout.addWidget(
            videos_group,
            stretch=1
        )

        # ======================================================
        # Augmentation + validation
        # ======================================================

        bottom_group = QGroupBox(
            "Dataset Options"
        )

        bottom_layout = QHBoxLayout(
            bottom_group
        )

        # ------------------------------------------------------
        # Augmentation
        # ------------------------------------------------------

        augmentation_group = QGroupBox(
            "Augmentation"
        )

        augmentation_layout = QVBoxLayout(
            augmentation_group
        )

        self.brightness_checkbox = QCheckBox(
            "Random Brightness / Contrast"
        )

        self.color_jitter_checkbox = QCheckBox(
            "Random Color Jitter"
        )

        self.flip_checkbox = QCheckBox(
            "Flip Left / Right"
        )

        # Default: NO augmentation.
        self.brightness_checkbox.setChecked(False)
        self.color_jitter_checkbox.setChecked(False)
        self.flip_checkbox.setChecked(False)

        augmentation_layout.addWidget(
            self.brightness_checkbox
        )

        augmentation_layout.addWidget(
            self.color_jitter_checkbox
        )

        augmentation_layout.addWidget(
            self.flip_checkbox
        )

        bottom_layout.addWidget(
            augmentation_group,
            stretch=2
        )

        # ------------------------------------------------------
        # Validation
        # ------------------------------------------------------

        validation_group = QGroupBox(
            "Validation Set"
        )

        validation_layout = QHBoxLayout(
            validation_group
        )

        validation_layout.addWidget(
            QLabel("Validation ratio:")
        )

        self.validation_spin = QSpinBox()

        self.validation_spin.setRange(
            0,
            90
        )

        self.validation_spin.setValue(
            0
        )

        self.validation_spin.setSuffix(" %")

        validation_layout.addWidget(
            self.validation_spin
        )

        validation_layout.addStretch()

        bottom_layout.addWidget(
            validation_group,
            stretch=1
        )

        layout.addWidget(
            bottom_group
        )

        # ======================================================
        # Output directory
        # ======================================================

        output_layout = QHBoxLayout()

        output_layout.addWidget(
            QLabel("Output:")
        )

        self.output_edit = QLabel(
            "No output directory selected"
        )

        self.output_edit.setFrameStyle(
            QFrame.Shape.StyledPanel
        )

        self.output_edit.setWordWrap(True)

        output_layout.addWidget(
            self.output_edit,
            stretch=1
        )

        browse_button = QPushButton(
            "Browse..."
        )

        browse_button.clicked.connect(
            self._choose_output_directory
        )

        output_layout.addWidget(
            browse_button
        )

        layout.addLayout(
            output_layout
        )

        # ======================================================
        # Buttons
        # ======================================================

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel_button = QPushButton(
            "Cancel"
        )

        cancel_button.clicked.connect(
            self.reject
        )

        export_button = QPushButton(
            "Export"
        )

        export_button.clicked.connect(
            self._export
        )

        export_button.setDefault(True)

        buttons.addWidget(
            cancel_button
        )

        buttons.addWidget(
            export_button
        )

        layout.addLayout(
            buttons
        )

    # ==========================================================
    # Layers / labels
    # ==========================================================

    def _load_layers(self):
        self._rebuild_labels()

    def _layers_changed(self, state):
        self._rebuild_labels()

    def _rebuild_labels(self):

        # Remove all existing label widgets.
        while self.labels_layout.count():

            item = self.labels_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.label_checkboxes.clear()

        selected_layers = [
            layer_name
            for layer_name, checkbox
            in self.layer_checkboxes.items()
            if checkbox.isChecked()
        ]

        row = 0
        column = 0

        for layer_name in selected_layers:

            layer = self.db.get_layer(
                layer_name
            )

            if layer is None:
                continue

            # Layer title.
            title = QLabel(
                f"<b>{layer_name.capitalize()}</b>"
            )

            self.labels_layout.addWidget(
                title,
                row,
                column,
            )

            row += 1

            for label in layer.labels:

                checkbox = QCheckBox(
                    label.name
                )

                checkbox.setChecked(True)

                checkbox.setProperty(
                    "layer_name",
                    layer_name,
                )

                checkbox.setProperty(
                    "label_name",
                    label.name,
                )

                self.label_checkboxes[
                    (layer_name, label.name)
                ] = checkbox

                self.labels_layout.addWidget(
                    checkbox,
                    row,
                    column,
                )

                row += 1

                # Two columns of labels.
                if row >= 7:
                    row = 0
                    column += 1

        self.labels_layout.setRowStretch(
            max(row, 0),
            1
        )

    # ==========================================================
    # Videos
    # ==========================================================

    def _load_videos(self):

        self.video_list.clear()

        media_items = self.db.get_all_media()

        for media in media_items:

            annotations = (
                self.db.get_media_annotations(
                    media.path
                )
            )

            if not annotations:
                continue

            item = QListWidgetItem(
                Path(media.path).name
            )

            item.setToolTip(
                media.path
            )

            item.setCheckState(
                Qt.CheckState.Checked
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                media.path
            )

            self.video_list.addItem(item)

    def _set_all_videos(self, checked):

        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )

        for i in range(
            self.video_list.count()
        ):
            self.video_list.item(
                i
            ).setCheckState(state)

    # ==========================================================
    # Output
    # ==========================================================

    def _choose_output_directory(self):

        directory = (
            QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory",
            )
        )

        if directory:
            self.output_edit.setText(
                directory
            )

    # ==========================================================
    # Export
    # ==========================================================

    def _export(self):

        output_dir = self.output_edit.text()

        if (
            not output_dir
            or output_dir
            == "No output directory selected"
        ):
            QMessageBox.warning(
                self,
                "Output Directory",
                "Please select an output directory.",
            )
            return

        selected_layers = [
            layer_name
            for layer_name, checkbox
            in self.layer_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_layers:

            QMessageBox.warning(
                self,
                "Layers",
                "Please select at least one layer.",
            )
            return

        selected_labels = [
            (layer_name, label_name)
            for (
                layer_name,
                label_name,
            ), checkbox
            in self.label_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_labels:

            QMessageBox.warning(
                self,
                "Labels",
                "Please select at least one label.",
            )
            return

        selected_videos = []

        for i in range(
            self.video_list.count()
        ):

            item = self.video_list.item(i)

            if (
                item.checkState()
                == Qt.CheckState.Checked
            ):

                selected_videos.append(
                    item.data(
                        Qt.ItemDataRole.UserRole
                    )
                )

        if not selected_videos:

            QMessageBox.warning(
                self,
                "Videos",
                "Please select at least one video.",
            )
            return

        output_format = (
            "detection"
            if self.detection_radio.isChecked()
            else "segmentation"
        )

        augmentations = []

        if self.brightness_checkbox.isChecked():
            augmentations.append(
                "brightness_contrast"
            )

        if self.color_jitter_checkbox.isChecked():
            augmentations.append(
                "color_jitter"
            )

        if self.flip_checkbox.isChecked():
            augmentations.append(
                "horizontal_flip"
            )

        self.export_settings = {
            "mode": (
                "combined"
                if self.combined_radio.isChecked()
                else "separate"
            ),
            "format": output_format,
            "layers": selected_layers,
            "labels": selected_labels,
            "videos": selected_videos,
            "output_dir": output_dir,
            "augmentations": augmentations,
            "validation_ratio": (
                self.validation_spin.value() / 100.0
            ),
        }

        self.accept()

    # ==========================================================

    def get_settings(self):

        return getattr(
            self,
            "export_settings",
            None,
        )