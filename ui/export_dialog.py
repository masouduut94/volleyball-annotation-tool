from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
                             QRadioButton, QCheckBox, QPushButton, QFileDialog, QListWidget,
                             QListWidgetItem, QFrame, QSpinBox, QMessageBox, QPlainTextEdit)

from .export_tooltip_texts import *
from .utils import create_help_button

SUMMARY_HELP = (
    "Live preview of the export configuration currently selected in this "
    "dialog. Dataset size and train/validation split are only known after "
    "the export finishes and will be shown then."
)

"""
Shared helpers for rendering a YOLO export summary.

`build_summary_text` is used in two places:
  1. Live, read-only preview inside YOLOExportDialog (settings only, no stats).
  2. `ExportSummaryDialog`, shown by MainWindow once the export worker
     finishes (settings + the actual dataset_size / split numbers).

Keeping this in one module means both views always agree on formatting.
"""

# Internal augmentation keys -> display names (must match YOLOExportDialog._export).
AUGMENTATION_LABELS = {
    "brightness_contrast": "Random Brightness/Contrast",
    "color_jitter": "Random Color Jitter",
    "horizontal_flip": "Flip Left/Right",
}

_LABEL_WIDTH = 18  # column width for the "Key:" part of each row


def _kv(label, value):
    return f"  {label:<{_LABEL_WIDTH}}{value}"


def build_summary_text(settings, stats=None):
    """
    Build the plain-text summary block.

    `settings` is the dict shape produced by YOLOExportDialog (mode, format,
    layers, labels, videos, output_dir, augmentations, validation_ratio).

    `stats`, if provided, is a dict with the *actual* results of a completed
    export:
        {
            "annotated_frames": int,
            "original_images":  int,
            "augmented_images": int,
            "total_images":     int,
            "train_images":     int,
            "val_images":       int,
        }
    When `stats` is None, only the settings sections are rendered (used for
    the live in-dialog preview, before anything has been exported yet).
    """

    lines = []

    # ------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------
    lines.append("EXPORT")
    lines.append(_kv("Mode:", settings["mode"].capitalize()))
    lines.append(_kv("Format:", settings["format"].capitalize()))

    # ------------------------------------------------------------
    # SELECTION
    # ------------------------------------------------------------
    lines.append("")
    lines.append("SELECTION")

    layer_names = ", ".join(name.capitalize() for name in settings["layers"]) or "None"
    lines.append(_kv("Layers:", layer_names))

    # settings["labels"] is a list of (layer_name, label_name) tuples in the
    # exact order the checkboxes were built in (layer order, then label order
    # within each layer) -- so this already reflects "actual order".
    label_names = [name for _, name in settings["labels"]]
    lines.append(_kv(f"Labels ({len(label_names)}):", ", ".join(label_names) if label_names else "None"))

    lines.append(_kv("Videos:", f"{len(settings['videos'])} selected"))

    # ------------------------------------------------------------
    # OPTIONS (augmentation + validation split, as configured)
    # ------------------------------------------------------------
    lines.append("")
    lines.append("OPTIONS")

    aug_names = [AUGMENTATION_LABELS.get(a, a) for a in settings.get("augmentations", [])]
    lines.append(_kv("Augmentations:", ", ".join(aug_names) if aug_names else "None"))
    lines.append(_kv("Validation ratio:", f"{round(settings.get('validation_ratio', 0) * 100)}%"))

    # ------------------------------------------------------------
    # OUTPUT
    # ------------------------------------------------------------
    lines.append("")
    lines.append("OUTPUT")
    output_dir = settings.get("output_dir") or ""
    dataset_name = Path(output_dir).name if output_dir else "(not selected)"
    lines.append(_kv("Dataset:", dataset_name))

    # ------------------------------------------------------------
    # DATASET SIZE + SPLIT (only once the export has actually run)
    # ------------------------------------------------------------
    if stats:
        lines.append("")
        lines.append("DATASET SIZE")
        lines.append(_kv("Total annotations:", stats.get("total_annotations", "-")))
        lines.append(
            _kv("Layer Counts:", " - ".join(
                f"{k}({v})"
                for k, v in stats['layers_counts'].items()
            )
                )
        )
        lines.append(
            _kv("Label Counts:", " - ".join(
                f"{k}({v})"
                for k, v in stats['labels_counts'].items()
            )
                )
        )

        lines.append(_kv("Original images:", stats.get("original_images", "-")))
        lines.append(_kv("Augmented images:", stats.get("augmented_images", "-")))
        lines.append(_kv("Total images:", stats.get("total_images", "-")))

        lines.append("")
        lines.append("SPLIT")
        lines.append(_kv("Train:", stats.get("train_images", "-")))
        lines.append(_kv("Validation:", stats.get("val_images", "-")))

    return "\n".join(lines)


class ExportSummaryDialog(QDialog):
    """
    Read-only popup with the formatted summary. Used for:
      - the final "export finished" report (settings + stats), and
      - optionally, a "view full summary" popup from the dialog's info button.
    """

    def __init__(self, settings, stats=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Export Complete" if stats else "Export Summary")
        self.resize(550, 620)

        layout = QVBoxLayout(self)

        heading = QLabel(
            "<b>YOLO dataset exported successfully.</b>" if stats
            else "<b>Export configuration</b>"
        )
        layout.addWidget(heading)

        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(build_summary_text(settings, stats))

        mono_font = QFont("Courier New")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        text_edit.setFont(mono_font)

        layout.addWidget(text_edit, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_row.addWidget(ok_button)
        layout.addLayout(button_row)


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
        self.resize(850, 850)

        self.layer_checkboxes = {}
        self.label_checkboxes = {}

        self._create_ui()
        self._load_layers()
        self._load_videos()
        self._update_summary()

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
        mode_tooltip = create_help_button(EXPORT_MODE_HELP)

        self.combined_radio = QRadioButton("Combined dataset")
        self.separate_radio = QRadioButton("Separate datasets")
        self.combined_radio.setChecked(True)

        self.combined_radio.toggled.connect(self._update_summary)

        mode_layout.addWidget(self.combined_radio)
        mode_layout.addWidget(self.separate_radio)
        mode_layout.addWidget(mode_tooltip)

        # ------------------------------------------------------
        # Annotation format
        # ------------------------------------------------------

        format_group = QGroupBox("Annotation Format")

        format_layout = QVBoxLayout(format_group)
        self.detection_radio = QRadioButton("YOLO Detection (Bounding Boxes)")
        self.segmentation_radio = QRadioButton("YOLO Segmentation (Polygons)")
        self.detection_radio.setChecked(True)
        format_tooltip = create_help_button(ANNOTATION_FORMAT_HELP)

        self.detection_radio.toggled.connect(self._update_summary)

        format_layout.addWidget(self.detection_radio)
        format_layout.addWidget(self.segmentation_radio)
        format_layout.addWidget(format_tooltip)

        top_layout.addWidget(mode_group, stretch=1)
        top_layout.addWidget(format_group, stretch=1)
        layout.addWidget(top_group)

        # ======================================================
        # Layers + Labels
        # ======================================================

        selection_group = QGroupBox("Layers and Labels")
        selection_layout = QHBoxLayout(selection_group)

        # ------------------------------------------------------
        # Layers
        # ------------------------------------------------------

        layers_group = QGroupBox("Layers")
        layers_layout = QVBoxLayout(layers_group)

        for layer_name in self.LAYERS:
            checkbox = QCheckBox(layer_name.capitalize())
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._layers_changed)
            self.layer_checkboxes[layer_name] = checkbox
            layers_layout.addWidget(checkbox)

        layer_tooltip = create_help_button(LAYERS_HELP)
        layers_layout.addWidget(layer_tooltip, stretch=1)

        layers_layout.addStretch()

        # ------------------------------------------------------
        # Labels
        # ------------------------------------------------------

        labels_group = QGroupBox("Labels")
        self.labels_layout = QGridLayout(labels_group)

        selection_layout.addWidget(layers_group, stretch=1)
        selection_layout.addWidget(labels_group, stretch=3)

        self.labels_group = labels_group

        # labels_tooltip = create_help_button(LABELS_HELP)
        # layers_layout.addWidget(labels_tooltip, stretch=1)
        layout.addWidget(selection_group)

        # ======================================================
        # Videos
        # ======================================================

        videos_group = QGroupBox("Videos / Media")

        videos_layout = QVBoxLayout(videos_group)
        self.video_list = QListWidget()
        self.video_list.itemChanged.connect(self._update_summary)
        videos_layout.addWidget(self.video_list)
        video_buttons = QHBoxLayout()
        select_all_videos = QPushButton("Select All")
        select_all_videos.clicked.connect(lambda: self._set_all_videos(True))

        deselect_all_videos = QPushButton("Deselect All")
        deselect_all_videos.clicked.connect(lambda: self._set_all_videos(False))

        video_buttons.addWidget(select_all_videos)
        video_buttons.addWidget(deselect_all_videos)
        video_buttons.addStretch()
        videos_layout.addLayout(video_buttons)

        video_tooltip = create_help_button(VIDEOS_HELP)
        videos_layout.addWidget(video_tooltip, stretch=1)
        layout.addWidget(videos_group, stretch=1)

        # ======================================================
        # Augmentation + validation
        # ======================================================

        bottom_group = QGroupBox("Dataset Options")

        bottom_layout = QHBoxLayout(bottom_group)

        # ------------------------------------------------------
        # Augmentation
        # ------------------------------------------------------

        augmentation_group = QGroupBox("Augmentation")

        augmentation_layout = QVBoxLayout(augmentation_group)
        self.brightness_checkbox = QCheckBox("Random Brightness / Contrast")
        self.color_jitter_checkbox = QCheckBox("Random Color Jitter")
        self.flip_checkbox = QCheckBox("Flip Left / Right")

        # Default: NO augmentation.
        self.brightness_checkbox.setChecked(False)
        self.color_jitter_checkbox.setChecked(False)
        self.flip_checkbox.setChecked(False)

        self.brightness_checkbox.stateChanged.connect(self._update_summary)
        self.color_jitter_checkbox.stateChanged.connect(self._update_summary)
        self.flip_checkbox.stateChanged.connect(self._update_summary)

        augmentation_layout.addWidget(self.brightness_checkbox)
        augmentation_layout.addWidget(self.color_jitter_checkbox)
        augmentation_layout.addWidget(self.flip_checkbox)

        augmentation_tooltip = create_help_button(AUGMENTATION_HELP)
        augmentation_layout.addWidget(augmentation_tooltip, stretch=1)

        bottom_layout.addWidget(augmentation_group, stretch=2)

        # ------------------------------------------------------
        # Validation
        # ------------------------------------------------------

        validation_group = QGroupBox("Validation Set")
        validation_layout = QHBoxLayout(validation_group)
        validation_layout.addWidget(QLabel("Validation ratio:"))

        self.validation_spin = QSpinBox()
        self.validation_spin.setRange(0, 90)
        self.validation_spin.setValue(0)
        self.validation_spin.setSuffix(" %")
        self.validation_spin.valueChanged.connect(self._update_summary)

        validation_layout.addWidget(self.validation_spin)
        validation_tooltip = create_help_button(VALIDATION_HELP)
        validation_layout.addWidget(validation_tooltip, stretch=1)
        validation_layout.addStretch()

        bottom_layout.addWidget(validation_group, stretch=1)
        layout.addWidget(bottom_group)

        # ======================================================
        # Output directory
        # ======================================================

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

        # ======================================================
        # Summary (live preview of everything selected above)
        # ======================================================

        # summary_group = QGroupBox("Summary")
        # summary_layout = QVBoxLayout(summary_group)
        #
        # summary_header = QHBoxLayout()
        # summary_header.addStretch()
        # summary_header.addWidget(create_help_button(SUMMARY_HELP))
        # summary_layout.addLayout(summary_header)
        #
        # self.summary_text = QPlainTextEdit()
        # self.summary_text.setReadOnly(True)
        # self.summary_text.setFixedHeight(250)
        #
        # mono_font = QFont("Courier New")
        # mono_font.setStyleHint(QFont.StyleHint.Monospace)
        # self.summary_text.setFont(mono_font)
        #
        # summary_layout.addWidget(self.summary_text)
        # layout.addWidget(summary_group)

        # ======================================================
        # Buttons
        # ======================================================

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        export_button = QPushButton("Export")
        export_button.clicked.connect(self._export)
        export_button.setDefault(True)
        buttons.addWidget(cancel_button)
        buttons.addWidget(export_button)
        layout.addLayout(buttons)

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

            layer = self.db.get_layer(layer_name)

            if layer is None:
                continue

            # Layer title.
            title = QLabel(f"<b>{layer_name.capitalize()}</b>")

            self.labels_layout.addWidget(title, row, column)

            row += 1

            for label in layer.labels:

                checkbox = QCheckBox(label.name)

                checkbox.setChecked(True)

                checkbox.setProperty("layer_name", layer_name)

                checkbox.setProperty("label_name", label.name)

                checkbox.stateChanged.connect(self._update_summary)

                self.label_checkboxes[
                    (layer_name, label.name)
                ] = checkbox

                self.labels_layout.addWidget(checkbox, row, column)

                row += 1

                # Two columns of labels.
                if row >= 7:
                    row = 0
                    column += 1

        self.labels_layout.setRowStretch(max(row, 0), 1)

        # Rebuilding replaces every label checkbox, so refresh the preview.
        self._update_summary()

    # ==========================================================
    # Videos
    # ==========================================================

    def _load_videos(self):

        self.video_list.clear()
        media_items = self.db.get_all_media()

        for media in media_items:

            annotations = self.db.get_media_annotations(media.path)

            if not annotations:
                continue

            item = QListWidgetItem(Path(media.path).name)
            item.setToolTip(media.path)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, media.path)
            self.video_list.addItem(item)

    def _set_all_videos(self, checked):

        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )

        for i in range(self.video_list.count()):
            self.video_list.item(i).setCheckState(state)

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
            self.output_edit.setText(directory)
            self._update_summary()

    # ==========================================================
    # Summary
    # ==========================================================

    def _collect_settings(self):
        """
        Snapshot every control's current value into the settings dict shape.
        Used both for the live summary preview (no validation) and, after
        validation, as the final settings returned by get_settings().
        """

        selected_layers = [
            layer_name
            for layer_name, checkbox
            in self.layer_checkboxes.items()
            if checkbox.isChecked()
        ]

        selected_labels = [
            (layer_name, label_name)
            for (layer_name, label_name), checkbox
            in self.label_checkboxes.items()
            if checkbox.isChecked()
        ]

        selected_videos = []

        for i in range(self.video_list.count()):

            item = self.video_list.item(i)

            if item.checkState() == Qt.CheckState.Checked:
                selected_videos.append(
                    item.data(Qt.ItemDataRole.UserRole)
                )

        output_dir = self.output_edit.text()

        if output_dir == "No output directory selected":
            output_dir = ""

        augmentations = []

        if self.brightness_checkbox.isChecked():
            augmentations.append("brightness_contrast")

        if self.color_jitter_checkbox.isChecked():
            augmentations.append("color_jitter")

        if self.flip_checkbox.isChecked():
            augmentations.append("horizontal_flip")

        return {
            "mode": (
                "combined"
                if self.combined_radio.isChecked()
                else "separate"
            ),
            "format": (
                "detection"
                if self.detection_radio.isChecked()
                else "segmentation"
            ),
            "layers": selected_layers,
            "labels": selected_labels,
            "videos": selected_videos,
            "output_dir": output_dir,
            "augmentations": augmentations,
            "validation_ratio": self.validation_spin.value() / 100.0,
        }

    def _update_summary(self):

        # Widgets may not exist yet the very first time this fires during
        # __init__ (signals connected before other widgets are built).
        if not hasattr(self, "summary_text"):
            return

        settings = self._collect_settings()
        self.summary_text.setPlainText(build_summary_text(settings))

    # ==========================================================
    # Export
    # ==========================================================

    def _export(self):

        settings = self._collect_settings()

        if not settings["output_dir"]:
            QMessageBox.warning(
                self,
                "Output Directory",
                "Please select an output directory.",
            )
            return

        if not settings["layers"]:
            QMessageBox.warning(
                self,
                "Layers",
                "Please select at least one layer.",
            )
            return

        if not settings["labels"]:
            QMessageBox.warning(
                self,
                "Labels",
                "Please select at least one label.",
            )
            return

        if not settings["videos"]:
            QMessageBox.warning(
                self,
                "Videos",
                "Please select at least one video.",
            )
            return

        self.export_settings = settings

        self.accept()

    # ==========================================================

    def get_settings(self):

        return getattr(self, "export_settings", None)
