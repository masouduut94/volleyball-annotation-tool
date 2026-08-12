# ui/bottom_toolbar.py

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QLabel
)


class BottomToolbar(QWidget):
    """
    Bottom toolbar for frame navigation and controls.

    This toolbar provides:
    - Previous/Next frame navigation
    - Frame number display and input
    - Total frames display
    - Keyboard shortcuts integration

    Signals:
        previousFrame: Emitted when previous frame is requested
        nextFrame: Emitted when next frame is requested
        gotoFrame: Emitted when a specific frame is requested (int)
    """

    previousFrame = pyqtSignal()
    nextFrame = pyqtSignal()
    gotoFrame = pyqtSignal(int)

    def __init__(self, parent=None):
        """
        Initialize the bottom toolbar.

        Args:
            parent: Parent widget (typically the main window)
        """
        super().__init__(parent)

        self.main_window = parent

        # Set up the UI
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Create and arrange all UI elements."""
        self.setObjectName("bottomToolbar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Create navigation buttons
        self.prev_btn = self._create_navigation_button(
            "◀ Previous",
            "Previous frame (A)",
            self.main_window.previous_frame
        )

        self.next_btn = self._create_navigation_button(
            "Next ▶",
            "Next frame (D)",
            self.main_window.next_frame
        )

        # Separator
        separator1 = QLabel("|")
        separator1.setObjectName("separator_label")

        # Frame navigation controls
        frame_label = QLabel("Frame")
        frame_label.setObjectName("frame_label")

        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(0)
        self.frame_spin.setToolTip("Jump to frame number")
        self.frame_spin.valueChanged.connect(self._on_frame_spin_changed)

        # Total frames display
        separator2 = QLabel("/")
        separator2.setObjectName("separator_label")

        self.total_label = QLabel("0")
        self.total_label.setObjectName("total_label")

        # Add widgets to layout
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.next_btn)
        layout.addWidget(separator1)
        layout.addWidget(frame_label)
        layout.addWidget(self.frame_spin)
        layout.addWidget(separator2)
        layout.addWidget(self.total_label)
        layout.addStretch()

    @staticmethod
    def _create_navigation_button(text, tooltip, callback):
        """
        Create a styled navigation button.

        Args:
            text (str): Button text
            tooltip (str): Tooltip text
            callback: Function to call when button is clicked

        Returns:
            QPushButton: Styled navigation button
        """
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        return btn

    def _apply_styles(self):
        """Apply consistent styling to all toolbar elements."""
        self.setStyleSheet("""
            QWidget#bottomToolbar {
                background-color: #2b2b2b;
                border-top: 1px solid #3c3c3c;
                padding: 5px 10px;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border-color: #666;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666;
                border-color: #3c3c3c;
            }
            QSpinBox {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 12px;
                min-width: 80px;
            }
            QSpinBox:hover {
                border-color: #666;
            }
            QSpinBox:focus {
                border-color: #4a90d9;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3c3c3c;
                border: none;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #4a4a4a;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 12px;
            }
            QLabel#total_label {
                color: #888;
                font-weight: 300;
            }
            QLabel#frame_label {
                color: #888;
                font-weight: 300;
                margin-right: 4px;
            }
            QLabel#separator_label {
                color: #555;
                font-weight: 300;
                margin: 0 2px;
            }
        """)

    def _on_frame_spin_changed(self, value):
        """
        Handle frame spin box value changes.

        Args:
            value (int): New frame number
        """
        self.gotoFrame.emit(value)

    def set_frame_range(self, max_value):
        """
        Set the maximum frame number.

        Args:
            max_value (int): Maximum frame number
        """
        self.frame_spin.setMaximum(max_value)
        self.total_label.setText(f"/ {max_value + 1}")

    def set_current_frame(self, frame_number):
        """
        Update the current frame display.

        Args:
            frame_number (int): Current frame number
        """
        self.frame_spin.blockSignals(True)
        self.frame_spin.setValue(frame_number)
        self.frame_spin.blockSignals(False)

    def get_current_frame(self):
        """
        Get the current frame number.

        Returns:
            int: Current frame number
        """
        return self.frame_spin.value()

    def set_total_frames(self, total):
        """
        Set the total number of frames.

        Args:
            total (int): Total number of frames
        """
        self.total_label.setText(f"/ {total}")

    def update_frame_display(self, current_frame, total_frames):
        """
        Update both current frame and total frames display.

        Args:
            current_frame (int): Current frame number
            total_frames (int): Total number of frames
        """
        self.set_frame_range(total_frames - 1)
        self.set_current_frame(current_frame)