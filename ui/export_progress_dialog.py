from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
)


class ExportProgressDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle(
            "Exporting YOLO Dataset"
        )

        self.setFixedSize(
            420,
            150,
        )

        self.setWindowModality(
            Qt.WindowModality.ApplicationModal
        )

        layout = QVBoxLayout(self)

        self.status_label = QLabel(
            "Preparing export..."
        )

        layout.addWidget(
            self.status_label
        )

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(0)

        layout.addWidget(
            self.progress_bar
        )

        self.cancel_button = QPushButton(
            "Cancel"
        )

        layout.addWidget(
            self.cancel_button
        )

        self._cancelled = False

    # ==========================================================

    def set_progress(
            self,
            value,
    ):

        self.progress_bar.setValue(
            value
        )

        self.status_label.setText(
            f"Exporting dataset... {value}%"
        )

    # ==========================================================

    def set_finished(self):

        self.status_label.setText(
            "Export completed."
        )

        self.progress_bar.setValue(
            100
        )

        self.cancel_button.setEnabled(
            False
        )

    # ==========================================================

    def set_cancelled(self):

        self.status_label.setText(
            "Export cancelled."
        )

        self.cancel_button.setEnabled(
            False
        )

    # ==========================================================

    def set_error(self, message):

        self.status_label.setText(
            "Export failed."
        )

        self.cancel_button.setEnabled(
            False
        )

        self.error_message = message