# ui/bottom_toolbar.py

from PyQt6.QtCore import pyqtSignal, QSize, Qt, QPoint, QRectF, QPointF
from PyQt6.QtGui import QIcon, QPainter, QColor, QFont, QPen
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QSpinBox, QLabel, QSlider, QStyleOptionSlider)

from .utils import create_navigation_button

STATE_COLORS = {
    "play": "#3DDC84",
    "no-play": "#555A66",
    "service": "#FF7A29",
    "unknown": "#3A3D46",
}


class FrameSlider(QSlider):
    """
    QSlider that displays the current frame number
    directly above the slider handle with color coding.
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

        # Initialize these FIRST — paintEvent can fire before the rest of
        # __init__ runs (e.g. as soon as the widget is added to a layout),
        # so anything paintEvent touches must exist before that can happen.
        self.segments = []  # list of (start_frame, end_frame, state, source)
        self._drag_started = False
        self._label_color = "#FFFFFF"

        self.setMouseTracking(True)

        # Create a label to show the frame number
        self.frame_label = QLabel(self)
        self.frame_label.hide()
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Set up label styling
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        self.frame_label.setFont(font)
        self.frame_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                border: 2px solid white;
                border-radius: 12px;
                color: white;
                padding: 2px;
            }
        """)

        self.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self, value):
        self._update_label_position()
        self._update_label_color(value)
        self.frame_label.setText(f"{value}")
        self.frame_label.show()

    def _update_label_color(self, value):
        """Update label color based on current frame position in segments."""
        color = "#FFFFFF"
        for start, end, state, source in self.segments:  # was: start, end, state
            if start <= value <= end:
                color = STATE_COLORS.get(state, "#FFFFFF")
                break

        self._label_color = color
        self.frame_label.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 180);
                border: 2px solid {color};
                border-radius: 12px;
                color: {color};
                padding: 2px;
            }}
        """)

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
        label_height = 30

        x = handle_rect.center().x() - label_width // 2
        y = handle_rect.top() - label_height - 5  # 5px gap above handle

        # Ensure label stays within widget bounds
        x = max(0, min(x, self.width() - label_width))
        y = max(0, y)

        self.frame_label.setGeometry(x, y, label_width, label_height)

    def set_segments(self, segments):
        """segments: list of (start_frame, end_frame, state) tuples."""
        self.segments = segments or []
        self.update()


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        segments = getattr(self, "segments", [])

        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = self.style()

        groove_rect = style.subControlRect(
            style.ComplexControl.CC_Slider,
            opt,
            style.SubControl.SC_SliderGroove,
            self
        )
        track_rect = QRectF(
            groove_rect.left(),
            groove_rect.center().y() - 4,
            groove_rect.width(),
            8
        )

        # Base (unclassified) track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(STATE_COLORS["unknown"]))
        painter.drawRoundedRect(track_rect, 4, 4)

        span = max(1, self.maximum() - self.minimum())

        def frame_to_x(frame):
            ratio = (frame - self.minimum()) / span
            return track_rect.left() + ratio * track_rect.width()

        # Classified windows
        for start, end, state, source in segments:  # was: start, end, state
            x1 = frame_to_x(start)
            x2 = frame_to_x(end + 1)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(STATE_COLORS.get(state, STATE_COLORS["unknown"])))
            rect = QRectF(x1, track_rect.top(), max(2.0, x2 - x1), track_rect.height())
            painter.drawRoundedRect(rect, 2, 2)

            if source == "manual":
                # Outline confirmed ground-truth tags so they read as distinct
                # from AI-generated guesses.
                painter.setPen(QPen(QColor("#FFFFFF"), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, 2, 2)

            if state == "service":
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#FFD814"))
                painter.drawRect(QRectF(x1, track_rect.top() - 3, 2, track_rect.height() + 6))

        # Handle
        handle_rect = style.subControlRect(
            style.ComplexControl.CC_Slider,
            opt,
            style.SubControl.SC_SliderHandle,
            self
        )

        current_value = self.value()
        handle_color = "#FFFFFF"
        for start, end, state, source in self.segments:  # was: start, end, state
            if start <= current_value <= end:
                handle_color = STATE_COLORS.get(state, "#FFFFFF")
                break

        painter.setBrush(QColor(handle_color))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawEllipse(handle_rect.center(), 7, 7)

    def _get_frame_from_pos(self, pos):
        """Calculate frame number from mouse click position."""
        if self.maximum() <= self.minimum():
            return self.minimum()

        # Get the groove rectangle
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = self.style()

        groove_rect = style.subControlRect(
            style.ComplexControl.CC_Slider,
            opt,
            style.SubControl.SC_SliderGroove,
            self
        )

        # Calculate position within the groove
        x = pos.x()
        groove_left = groove_rect.left()
        groove_right = groove_rect.right()
        groove_width = groove_right - groove_left

        # Clamp to groove bounds
        x = max(groove_left, min(groove_right, x))

        # Calculate ratio and corresponding frame
        ratio = (x - groove_left) / max(1, groove_width)
        frame = self.minimum() + round(ratio * (self.maximum() - self.minimum()))

        return max(self.minimum(), min(self.maximum(), frame))

    def mousePressEvent(self, event):
        """Handle mouse press to jump to click position."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_started = True

            # Calculate frame from click position
            frame = self._get_frame_from_pos(event.position().toPoint())

            # Position label at click point instead of above handle
            label_width = 80
            label_height = 30

            click_x = event.position().x() - label_width // 2
            click_y = 10  # Fixed position near top

            # Ensure label stays within widget bounds
            click_x = max(0, int(min(click_x, self.width() - label_width)))
            self.frame_label.setGeometry(click_x, click_y, label_width, label_height)

            # Update the slider value
            self.blockSignals(True)
            self.setValue(frame)
            self.blockSignals(False)

            self._update_label_color(frame)
            self.frame_label.setText(f"{frame}")
            self.frame_label.show()

            # Emit the value changed signal manually
            self.valueChanged.emit(frame)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update label position when dragging."""
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_started:
            current_value = self.value()
            self._update_label_color(current_value)
            self.frame_label.setText(f"{current_value}")
            self.frame_label.show()

            # Update handle position during drag
            frame = self._get_frame_from_pos(event.position().toPoint())
            self.blockSignals(True)
            self.setValue(frame)
            self.blockSignals(False)
            self.valueChanged.emit(frame)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Keep label visible after release."""
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_started = False

            # Final update to ensure label is at correct position
            current_value = self.value()
            self._update_label_position()
            self._update_label_color(current_value)
            self.frame_label.setText(f"{current_value}")
            self.frame_label.show()

    def leaveEvent(self, event):
        self.frame_label.hide()
        self._drag_started = False
        super().leaveEvent(event)

    def enterEvent(self, event):
        """Show label when mouse enters the widget."""
        super().enterEvent(event)
        current_value = self.value()
        self._update_label_color(current_value)
        self.frame_label.setText(f"{current_value}")
        self._update_label_position()
        self.frame_label.show()

    def wheelEvent(self, event):
        """Handle mouse wheel scrolling."""
        super().wheelEvent(event)
        current_value = self.value()
        self._update_label_color(current_value)
        self.frame_label.setText(f"{current_value}")
        self._update_label_position()
        self.frame_label.show()


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
    ICON_SIZE = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

        self._setup_ui()

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

        self.double_prev_btn = create_navigation_button(
            tooltip="Previous frame X15 (Q)",
            icon_path="./resources/icons/bottom_toolbar/prevprev.png",
            callback=self.main_window.previous_15_frame,
            object_name="navigationButton",
            icon_size=self.ICON_SIZE,
        )

        self.prev_btn = create_navigation_button(
            tooltip="Previous frame (A)",
            icon_path="./resources/icons/bottom_toolbar/prev.png",
            callback=self.main_window.previous_frame,
            object_name="navigationButton",
            icon_size=self.ICON_SIZE,
        )

        self.play_btn = create_navigation_button(
            tooltip="Play (Space)",
            icon_path="./resources/icons/bottom_toolbar/play.png",
            callback=self.main_window.toggle_playback,
            object_name="navigationButton",
            icon_size=self.ICON_SIZE,
        )

        self.next_btn = create_navigation_button(
            tooltip="Next frame (D)",
            icon_path="./resources/icons/bottom_toolbar/next.png",
            callback=self.main_window.next_frame,
            object_name="navigationButton",
            icon_size=self.ICON_SIZE,
        )

        self.double_next_btn = create_navigation_button(
            tooltip="Next frame X15 (D)",
            icon_path="./resources/icons/bottom_toolbar/nextnext.png",
            callback=self.main_window.next_15_frame,
            object_name="navigationButton",
            icon_size=self.ICON_SIZE,
        )

        # ---------------------------------------------------------
        # Frame seek bar
        # ---------------------------------------------------------

        self.frame_slider = FrameSlider(Qt.Orientation.Horizontal)

        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.setValue(0)

        self.frame_slider.setToolTip("Seek to frame")
        # Set tooltip replace with ToolTipManager

        # Give the slider a reasonable width
        self.frame_slider.setMinimumWidth(250)
        self.frame_slider.setMaximumWidth(500)
        self.frame_slider.setMinimumHeight(50)

        # Update frame when slider is moved
        self.frame_slider.valueChanged.connect(self._on_slider_changed)

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

        self.frame_spin.setToolTip("Jump to frame number")

        self.frame_spin.valueChanged.connect(self._on_frame_spin_changed)

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
        layout.addWidget(self.play_btn)
        layout.addWidget(self.next_btn)
        layout.addWidget(self.double_next_btn)

        layout.addWidget(self.frame_slider)

        layout.addWidget(separator1)

        layout.addWidget(frame_label)
        layout.addWidget(self.frame_spin)

        layout.addWidget(separator2)
        layout.addWidget(self.total_label)

        # ---------------------------------------------------------
        # Right stretch
        # ---------------------------------------------------------

        layout.addStretch(1)

    def set_game_state_segments(self, segments):
        """segments: list of (start_frame, end_frame, state, source) tuples."""
        self.frame_slider.set_segments(segments)

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
        self.frame_slider.setRange(0, max_value)
        self.frame_spin.setRange(0, max_value)
        self.frame_slider.blockSignals(False)
        self.frame_spin.blockSignals(False)
        self.total_label.setText(f"/ {max_value + 1}")

    # -------------------------------------------------------------
    # Current frame
    # -------------------------------------------------------------

    def set_current_frame(self, frame_number):
        """
        Update both the spin box and slider.
        """

        frame_number = max(0, min(frame_number, self.frame_slider.maximum()))
        self.frame_slider.blockSignals(True)
        self.frame_spin.blockSignals(True)
        self.frame_slider.setValue(frame_number)
        self.frame_spin.setValue(frame_number)
        self.frame_slider.blockSignals(False)
        self.frame_spin.blockSignals(False)
        # Update the label color
        self.frame_slider._update_label_color(frame_number)

    def get_current_frame(self):
        """Return current frame number."""
        return self.frame_spin.value()

    def set_playback_state(self, is_playing: bool):
        """
        Update the play button icon and tooltip depending
        on the current playback state.
        """

        if is_playing:
            self.play_btn.setIcon(QIcon("./resources/icons/bottom_toolbar/pause.png"))
            self.play_btn.setToolTip("Pause (Space)")

        else:
            self.play_btn.setIcon(QIcon("./resources/icons/bottom_toolbar/play.png"))
            self.play_btn.setToolTip("Play (Space)")
