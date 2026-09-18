"""
Runtime theme switching. ThemeManager is a singleton QObject — call
ThemeManager.instance() from anywhere; never construct it directly.

Switching a theme does three things, in order:
  1. Colors.apply(palette) — mutates every attribute components.py reads.
  2. Rebuilds the full stylesheet and re-applies it at the QApplication
     level — Qt re-evaluates the whole stylesheet against every widget
     when it's replaced, so this re-styles the entire app in one shot.
  3. Emits themeChanged(theme_name) — for the few widgets that paint
     themselves manually with QPainter instead of via QSS (the Temporal
     Timeline canvas, the toggle switch itself), which need an explicit
     repaint since a stylesheet swap alone never touches hand-drawn pixels.

The chosen theme persists across launches via QSettings.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from PyQt6.QtWidgets import QApplication, QWidget

from .colors import Colors
from .palettes import PALETTES
from .theme import build_stylesheet

_SETTINGS_ORG = "VBAnnotator"
_SETTINGS_APP = "AnnotationPlatform"
_SETTINGS_KEY = "ui/theme"
DEFAULT_THEME = "dark"


class ThemeManager(QObject):
    themeChanged = pyqtSignal(str)  # "dark" | "light"

    _instance = None

    def __init__(self):
        super().__init__()
        self._current = DEFAULT_THEME

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    @property
    def current_theme(self) -> str:
        return self._current

    def load_saved_theme(self):
        """Call once, as early as possible (before any themed widget is
        constructed), to restore the user's last choice."""
        settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        saved = settings.value(_SETTINGS_KEY, DEFAULT_THEME)
        self.set_theme(saved if saved in PALETTES else DEFAULT_THEME, persist=False)

    def set_theme(self, name: str, persist: bool = True):
        if name not in PALETTES:
            raise ValueError(f"Unknown theme '{name}'. Valid options: {list(PALETTES)}")

        Colors.apply(PALETTES[name])
        self._current = name

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet())

        if persist:
            QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(_SETTINGS_KEY, name)

        self.themeChanged.emit(name)

    def toggle(self):
        self.set_theme("light" if self._current == "dark" else "dark")

def register_themed_widget(widget, style_fn):
    """
    Apply style_fn() to `widget` immediately, and keep re-applying it on
    every future theme change. Use this instead of a bare
    `self.setStyleSheet(xyz_style())` call in any widget's __init__ —
    the bare version freezes that widget at whichever theme was active
    the moment it was constructed, since nothing ever tells it to
    regenerate its stylesheet string later.
    """
    widget.setStyleSheet(style_fn())
    ThemeManager.instance().themeChanged.connect(lambda _: widget.setStyleSheet(style_fn()))

def repolish(widget: QWidget):
    """
    Fully re-evaluate `widget`'s stylesheet AND every one of its
    descendants, then repaint.

    QWidget.style().unpolish()/polish() only recomputes the ONE widget
    it's called on. That's enough for a rule that targets the widget
    directly ("#foo[active=true] { background: ... }"), but it does
    nothing for a rule that targets a DESCENDANT of it
    ("#foo[active=true] QPushButton { color: ... }") — the child keeps
    rendering stale styling until something else forces a full-tree
    restyle (which is exactly why toggling the app theme "fixes" a
    stuck row: QApplication.setStyleSheet() repolishes every widget in
    the app, children included).

    Any code that flips a dynamic property or objectName used inside a
    descendant-combinator selector should call this instead of hand
    rolling unpolish()/polish() on a single widget.
    """
    for w in (widget, *widget.findChildren(QWidget)):
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()
