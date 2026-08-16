# ui/bottom_toolbar.py

from PyQt6.QtCore import pyqtSignal, QSize, Qt, QPoint
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QLabel,
    QSlider,
    QToolTip, QStyleOptionSlider
)


class FrameSlider(QSlider):
    """
    QSlider that displays the current frame number
    directly above the slider handle.
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

        self.setMouseTracking(True)

        # Create a label to show the frame number
        self.frame_label = QLabel(self)
        self.frame_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 200);
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 4px;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        self.frame_label.hide()
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self, value):
        self._update_label_position()
        self.frame_label.setText(f"{value}")
        self.frame_label.show()

    def _update_label_position(self):
        """Position the label above the slider handle."""

        if self.maximum() <= self.minimum():
            return

        # Create a style option for the slider
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)

        style = self.style()

        # Get the handle rectangle
        handle_rect = style.subControlRect(
            style.ComplexControl.CC_Slider,
            opt,
            style.SubControl.SC_SliderHandle,
            self
        )

        # Position label above the handle
        label_width = 80
        label_height = 25

        x = handle_rect.center().x() - label_width // 2
        y = handle_rect.top() - label_height - 5  # 5px gap above handle

        # Ensure label stays within widget bounds
        x = max(0, min(x, self.width() - label_width))
        y = max(0, y)

        self.frame_label.setGeometry(x, y, label_width, label_height)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._update_label_position()
        self.frame_label.setText(f"{self.value()}")
        self.frame_label.show()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_label_position()
            self.frame_label.setText(f"{self.value()}")
            self.frame_label.show()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # Keep showing for a moment, then hide after a delay
        self.frame_label.show()

    def leaveEvent(self, event):
        self.frame_label.hide()
        super().leaveEvent(event)

class BottomToolbar(QWidget):
    """
    Bottom toolbar for frame navigation and controls.

    Provides:
    - Previous / next frame navigation
    - Previous / next 15 frames navigation
    - Interactive frame seek bar
    - Frame number display and input
    - Total frames display
    """

    previousFrame = pyqtSignal()
    nextFrame = pyqtSignal()
    gotoFrame = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.main_window = parent

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Create and arrange all UI elements."""

        self.setObjectName("bottomToolbar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ---------------------------------------------------------
        # Left stretch
        # ---------------------------------------------------------

        layout.addStretch(1)

        # ---------------------------------------------------------
        # Navigation buttons
        # ---------------------------------------------------------

        self.double_prev_btn = self._create_navigation_button(
            "",
            "Previous frame X15 (Q)",
            "./resources/icons/bottom_toolbar/prevprev.png",
            self.main_window.previous_15_frame,
        )

        self.prev_btn = self._create_navigation_button(
            "",
            "Previous frame (A)",
            "./resources/icons/bottom_toolbar/prev.png",
            self.main_window.previous_frame,
        )

        self.next_btn = self._create_navigation_button(
            "",
            "Next frame (D)",
            "./resources/icons/bottom_toolbar/next.png",
            self.main_window.next_frame,
        )

        self.double_next_btn = self._create_navigation_button(
            "",
            "Next frame X15 (D)",
            "./resources/icons/bottom_toolbar/nextnext.png",
            self.main_window.next_15_frame,
        )

        # ---------------------------------------------------------
        # Frame seek bar
        # ---------------------------------------------------------

        self.frame_slider = FrameSlider(Qt.Orientation.Horizontal)

        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.setValue(0)

        self.frame_slider.setToolTip("Seek to frame")

        # Give the slider a reasonable width
        self.frame_slider.setMinimumWidth(250)
        self.frame_slider.setMaximumWidth(500)
        self.frame_slider.setMinimumHeight(50)

        # Update frame when slider is moved
        self.frame_slider.valueChanged.connect(
            self._on_slider_changed
        )

        # ---------------------------------------------------------
        # Separator
        # ---------------------------------------------------------

        separator1 = QLabel("|")
        separator1.setObjectName("separator_label")

        # ---------------------------------------------------------
        # Frame number
        # ---------------------------------------------------------

        frame_label = QLabel("Frame")
        frame_label.setObjectName("frame_label")

        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(0)
        self.frame_spin.setMaximum(0)

        self.frame_spin.setToolTip(
            "Jump to frame number"
        )

        self.frame_spin.valueChanged.connect(
            self._on_frame_spin_changed
        )

        # ---------------------------------------------------------
        # Total frames
        # ---------------------------------------------------------

        separator2 = QLabel("/")
        separator2.setObjectName("separator_label")

        self.total_label = QLabel("0")
        self.total_label.setObjectName("total_label")

        # ---------------------------------------------------------
        # Add widgets
        # ---------------------------------------------------------

        layout.addWidget(self.double_prev_btn)
        layout.addWidget(self.prev_btn)

        layout.addWidget(self.frame_slider)

        layout.addWidget(self.next_btn)
        layout.addWidget(self.double_next_btn)

        layout.addWidget(separator1)

        layout.addWidget(frame_label)
        layout.addWidget(self.frame_spin)

        layout.addWidget(separator2)
        layout.addWidget(self.total_label)

        # ---------------------------------------------------------
        # Right stretch
        # ---------------------------------------------------------

        layout.addStretch(1)

    @staticmethod
    def _create_navigation_button(
            text: str,
            tooltip: str,
            icon_path: str,
            callback,
            icon_size=25,
    ):
        """Create a styled navigation button."""

        btn = QPushButton(text)

        btn.setToolTip(tooltip)

        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(
            QSize(icon_size, icon_size)
        )

        btn.clicked.connect(callback)

        return btn

    def _apply_styles(self):
        """Apply styling to toolbar elements."""

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
                margin: 10px 2px;
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

            QSlider {
                min-width: 250px;
                max-width: 500px;
            }

            QSlider::groove:horizontal {
                height: 5px;
                background: #444;
                border-radius: 2px;
            }

            QSlider::sub-page:horizontal {
                background: #4a90d9;
                border-radius: 2px;
            }

            QSlider::add-page:horizontal {
                background: #383838;
                border-radius: 2px;
            }

            QSlider::handle:horizontal {
                width: 13px;
                height: 13px;
                margin: -4px 0;
                background: #d0d0d0;
                border: 1px solid #777;
                border-radius: 6px;
            }

            QSlider::handle:horizontal:hover {
                background: #ffffff;
                border-color: #4a90d9;
            }

            QSpinBox {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 12px;
                min-width: 20px;
            }

            QSpinBox:hover {
                border-color: #666;
            }

            QSpinBox:focus {
                border-color: #4a90d9;
            }

            QSpinBox::up-button,
            QSpinBox::down-button {
                background-color: #3c3c3c;
                border: none;
                width: 16px;
            }

            QSpinBox::up-button:hover,
            QSpinBox::down-button:hover {
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

    # -------------------------------------------------------------
    # Slider
    # -------------------------------------------------------------

    def _on_slider_changed(self, value):
        """
        Called when the seek bar changes.

        This sends the selected frame to MainWindow.
        """

        # Avoid unnecessary navigation when the value
        # already represents the currently displayed frame.
        if value == self.frame_spin.value():
            return

        self.gotoFrame.emit(value)

    # -------------------------------------------------------------
    # Spin box
    # -------------------------------------------------------------

    def _on_frame_spin_changed(self, value):
        """
        Called when the frame number spin box changes.
        """

        # Keep slider synchronized with spin box.

        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(value)
        self.frame_slider.blockSignals(False)

        self.gotoFrame.emit(value)

    # -------------------------------------------------------------
    # Frame range
    # -------------------------------------------------------------

    def set_frame_range(self, max_value):
        """
        Set the maximum frame number.

        Example:
            100 frames -> range 0 ... 99
        """

        max_value = max(0, max_value)

        self.frame_slider.blockSignals(True)
        self.frame_spin.blockSignals(True)

        self.frame_slider.setRange(
            0,
            max_value,
        )

        self.frame_spin.setRange(
            0,
            max_value,
        )

        self.frame_slider.blockSignals(False)
        self.frame_spin.blockSignals(False)

        self.total_label.setText(
            f"/ {max_value + 1}"
        )

    # -------------------------------------------------------------
    # Current frame
    # -------------------------------------------------------------

    def set_current_frame(self, frame_number):
        """
        Update both the spin box and slider.
        """

        frame_number = max(
            0,
            min(
                frame_number,
                self.frame_slider.maximum(),
            ),
        )

        self.frame_slider.blockSignals(True)
        self.frame_spin.blockSignals(True)

        self.frame_slider.setValue(
            frame_number
        )

        self.frame_spin.setValue(
            frame_number
        )

        self.frame_slider.blockSignals(False)
        self.frame_spin.blockSignals(False)

    def get_current_frame(self):
        """Return current frame number."""

        return self.frame_spin.value()

    # -------------------------------------------------------------
    # Total frames
    # -------------------------------------------------------------
