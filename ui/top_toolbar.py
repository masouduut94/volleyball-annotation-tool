from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QToolBar, QMenu, QWidget, QHBoxLayout, QLabel, QSizePolicy

from .theme.theme_manager import ThemeManager, register_themed_widget
from .theme.toggle_switch import ThemeToggleSwitch
from .theme.theme import top_toolbar_style

class TopToolbar(QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

        self.setObjectName("topToolbar")
        register_themed_widget(self, top_toolbar_style)

        self._create_actions()
        self._add_actions_to_toolbar()
        self._add_theme_switcher()

    def _create_actions(self):
        self.open_images_action = QAction("Open Images", self)
        self.open_images_action.triggered.connect(self.main_window.open_images)
        self.open_video_action = QAction("Open Video", self)
        self.open_video_action.triggered.connect(self.main_window.open_video)
        self.clear_action = QAction("Clear", self)
        self.clear_action.triggered.connect(self.main_window.clear_current_frame_annotations)
        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self.main_window.save_annotations)

        self.export_menu = QMenu("Export", self)

        self.export_yolo_action = QAction("YOLO", self)
        self.export_yolo_action.triggered.connect(self.main_window.export_yolo)
        self.export_menu.addAction(self.export_yolo_action)

        self.export_videomae_action = QAction("VideoMAE", self)
        self.export_videomae_action.triggered.connect(self.main_window.export_videomae)
        self.export_menu.addAction(self.export_videomae_action)

    def _add_actions_to_toolbar(self):
        self.addAction(self.open_images_action)
        self.addAction(self.open_video_action)
        self.addAction(self.clear_action)
        self.addAction(self.save_action)
        self.addSeparator()
        self.addAction(self.export_menu.menuAction())

    def _add_theme_switcher(self):
        """Dark/Light toggle, right-aligned via an expanding spacer
        widget added just before it — the standard Qt pattern for
        pushing toolbar content to the far edge."""
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        container = QWidget()
        container.setObjectName("themeSwitcher")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self.theme_moon_label = QLabel("🌙")
        self.theme_switch = ThemeToggleSwitch()
        self.theme_sun_label = QLabel("☀️")

        layout.addWidget(self.theme_moon_label)
        layout.addWidget(self.theme_switch)
        layout.addWidget(self.theme_sun_label)

        self.addWidget(container)

        # Reflect whatever theme is already active (e.g. restored from
        # settings before this toolbar was even built) without an
        # animated transition on startup.
        self.theme_switch.setChecked(ThemeManager.instance().current_theme == "light")

        self.theme_switch.toggled.connect(self._on_theme_switch_toggled)
        ThemeManager.instance().themeChanged.connect(self._on_theme_changed_externally)

    @staticmethod
    def _on_theme_switch_toggled(checked):
        ThemeManager.instance().set_theme("light" if checked else "dark")

    def _on_theme_changed_externally(self, theme_name):
        """Keep the switch's visual state correct if the theme was ever
        changed some other way than this exact switch instance."""
        should_be_checked = theme_name == "light"
        if self.theme_switch.isChecked() != should_be_checked:
            self.theme_switch.blockSignals(True)
            self.theme_switch.setChecked(should_be_checked)
            self.theme_switch.blockSignals(False)