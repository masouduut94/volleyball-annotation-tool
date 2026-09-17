"""
Component-level QSS fragments.

IMPORTANT: every selector here is scoped with a `#<scope>` prefix, where
`scope` is the objectName of the container widget (e.g. "leftSidebar",
"rightSidebar"). This is what stops a bare `QPushButton {}` rule from
leaking into every button in the app once styles are centralized.

Each function returns a string. Compose them in theme.py.
"""

from .colors import Colors
from .typography import Typography


def default_text(scope: str) -> str:
    """
    Baseline text color for otherwise-unstyled widgets in this scope
    (plain QLabel, QCheckBox/QRadioButton, QToolButton).

    Every other rule in this file targets a specific #objectName
    (QLabel#title, QLabel#section, QLabel#headerTitle, QLabel#statusOk,
    ...). Anything WITHOUT one — "Frame", "Zoom", "Object Detection",
    every DetectionRow's plain name label, etc. — currently falls
    through to Qt's native widget style entirely unstyled. On Windows
    that resolves to the system palette's WindowText color (near-black),
    unreadable against this app's dark backgrounds; other platforms'
    native styles happened to default to something lighter, which is why
    this only surfaced on Windows.

    Declared as a TYPE selector (no #objectName) so it can never
    override the more specific ID-selector rules elsewhere in this file
    — in QSS, as in CSS, an ID selector always beats a type selector
    regardless of declaration order, so this is safe to add anywhere.
    """
    return f"""
    #{scope} QLabel {{
        color: {Colors.TEXT_PRIMARY};
        background: transparent;
    }}

    #{scope} QCheckBox, #{scope} QRadioButton {{
        color: {Colors.TEXT_PRIMARY};
    }}

    #{scope} QToolButton {{
        color: {Colors.TEXT_PRIMARY};
    }}
    """


def top_toolbar(scope: str) -> str:
    """Background, button, and label styling for the top toolbar,
    including the Dark/Light theme switcher container."""
    return f"""
    QToolBar#{scope} {{
        background: {Colors.BG_APP};
        border-bottom: 1px solid {Colors.BORDER};
        spacing: 4px;
        padding: 4px 6px;
    }}

    QToolBar#{scope} QToolButton {{
        color: {Colors.TEXT_PRIMARY};
        background: transparent;
        border-radius: 6px;
        padding: 4px 8px;
    }}

    QToolBar#{scope} QToolButton:hover {{
        background: {Colors.BG_HOVER};
    }}

    #{scope} QLabel {{
        color: {Colors.TEXT_PRIMARY};
        background: transparent;
        font-size: {Typography.SIZE_MD};
    }}
    """


def panel_base(scope: str) -> str:
    return f"""
    QWidget#{scope} {{
        background: {Colors.BG_APP};
        color: {Colors.TEXT_PRIMARY};
        font-size: {Typography.SIZE_SM};
    }}
    """


def section_title(scope: str) -> str:
    return f"""
    #{scope} QLabel#title {{
        font-size: {Typography.SIZE_LG};
        padding: 10px;
        margin-top: 10px;
        font-weight: {Typography.WEIGHT_BOLD_QSS};
        color: {Colors.TEXT_BRIGHT};
    }}

    #{scope} QLabel#section {{
        font-size: {Typography.SIZE_SM};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
        color: {Colors.TEXT_MUTED};
        margin-top: 10px;
    }}
    """


def header_label(scope: str) -> str:
    """SectionHeader title label used in right sidebar."""
    return f"""
    #{scope} QLabel#headerTitle {{
        color: {Colors.TEXT_HEADER};
        font-size: {Typography.SIZE_LG};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
        padding: 4px 2px 8px 2px;
    }}
    """


def separator(scope: str) -> str:
    return f"""
    #{scope} QFrame#line {{
        background: {Colors.LINE};
        max-height: 1px;
        min-height: 1px;
    }}

    #{scope} QFrame#divider {{
        color: {Colors.DIVIDER};
    }}
    """


def nav_row_button(scope: str) -> str:
    """Layer-row style nav buttons (left sidebar)."""
    return f"""
    #{scope} QPushButton {{
        background: transparent;
        border: none;
        padding: 10px 10px;
        text-align: left;
        border-radius: 8px;
        color: {Colors.TEXT_PRIMARY};
    }}

    #{scope} QPushButton:hover {{
        background: {Colors.BG_HOVER};
        border: 1px solid {Colors.ACCENT};
    }}

    #{scope} QPushButton#activeLayer {{
        background: {Colors.ACCENT};
        color: white;
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}
    """


def label_button(scope: str) -> str:
    return f"""
    #{scope} QPushButton#labelButton {{
        background: transparent;
        border: none;
        padding: 8px 10px;
        text-align: left;
        border-radius: 8px;
        color: {Colors.TEXT_PRIMARY};
    }}

    #{scope} QPushButton#labelButton:hover {{
        background: {Colors.ACCENT};
        color: white;
    }}

    #{scope} QPushButton#activeLabel {{
        background: {Colors.BG_SURFACE};
        border: 1px solid {Colors.ACCENT};
        border-radius: 8px;
        color: {Colors.TEXT_BRIGHT};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}
    """


def tool_toggle_button(scope: str) -> str:
    """Square icon toggle buttons (rectangle/polygon tool)."""
    return f"""
    #{scope} QPushButton#tool {{
        background: {Colors.BG_SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 10px;
        color: {Colors.TEXT_PRIMARY};
        margin: 0px;
        min-width: 42px;
        max-width: 42px;
        min-height: 42px;
        max-height: 42px;
    }}

    #{scope} QPushButton#tool:hover {{
        background: {Colors.BG_HOVER_ALT};
    }}

    #{scope} QPushButton#toolActive {{
        background: {Colors.ACCENT};
        border: 1px solid {Colors.ACCENT};
        border-radius: 10px;
        margin: 0px;
        color: white;
        min-width: 42px;
        max-width: 42px;
        min-height: 42px;
        max-height: 42px;
    }}
    """


def icon_toolbutton(scope: str) -> str:
    return f"""
    #{scope} QToolButton#ToolButton {{
        background-color: transparent;
        border: none;
        border-radius: 6px;
        padding: 0px;
    }}

    #{scope} QToolButton#ToolButton:hover {{
        background-color: #3a3a3a;
    }}
    
    #{scope} QToolButton#ToolButton:pressed {{
        background-color: #4a4a4a;
    }}
    """


def navigation_button(scope: str = "bottomToolbar") -> str:
    return f"""
    QWidget#{scope} QPushButton#navigationButton {{
        background-color: transparent;
        border: none;
        border-radius: 6px;
        padding: 0px;
    }}

    QWidget#{scope} QPushButton#navigationButton:hover {{
        background-color: #3a3a3a;
    }}

    QWidget#{scope} QPushButton#navigationButton:pressed {{
        background-color: #4a4a4a;
    }}
    """


def surface_button(scope: str) -> str:
    """Filled buttons used in right sidebar (Quick Annotate, Configurations, Run)."""
    return f"""
    #{scope} QPushButton {{
        background: {Colors.BG_SURFACE};
        color: #E6E6E6;
        border: 1px solid {Colors.BORDER};
        border-radius: 7px;
        font-weight: {Typography.WEIGHT_REGULAR};
    }}

    #{scope} QPushButton:hover {{
        background: {Colors.BG_SURFACE_HOVER};
        border-color: {Colors.BORDER_HOVER};
    }}

    #{scope} QPushButton:pressed {{
        background: {Colors.BG_SURFACE_PRESSED};
    }}
    """


def status_labels(scope: str) -> str:
    return f"""
    #{scope} QLabel#statusOk {{
        color: {Colors.SUCCESS};
        font-size: {Typography.SIZE_XS};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}

    #{scope} QLabel#statusWarn {{
        color: {Colors.WARNING};
        font-size: {Typography.SIZE_XS};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}
    """


def tooltip() -> str:
    """Not widget-scoped on purpose: QToolTip is a top-level popup, not a
    descendant of any widget, so scoping wouldn't work anyway. This one
    rule is safe/intended to be global."""
    return f"""
    QToolTip {{
        background-color: {Colors.TOOLTIP_BG};
        color: {Colors.TOOLTIP_TEXT};
        border: 1px solid {Colors.TOOLTIP_BORDER};
        padding: 6px 10px;
        border-radius: 6px;
        font-size: {Typography.SIZE_XS};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}
    """


def detection_row(scope: str) -> str:
    """Card-style background for each DetectionRow in the right sidebar."""
    return f"""
    #{scope} QWidget#detectionRow {{
        background: {Colors.BG_SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
    }}

    #{scope} QWidget#detectionRow:hover {{
        border-color: {Colors.BORDER_HOVER};
    }}
    """


def icon_button(scope: str) -> str:
    """Small square icon/text-only buttons, e.g. the inline model-path
    picker ("…") in each DetectionRow."""
    return f"""
    #{scope} QPushButton#pathButton {{
        background: transparent;
        border: 1px solid {Colors.BORDER};
        border-radius: 6px;
        color: {Colors.TEXT_MUTED};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}

    #{scope} QPushButton#pathButton:hover {{
        background: {Colors.BG_HOVER_ALT};
        border-color: {Colors.BORDER_HOVER};
        color: {Colors.TEXT_PRIMARY};
    }}
    """


def confirmation_bar(scope: str = "confirmationBar") -> str:
    return f"""
    QWidget#{scope} {{
        background: {Colors.BG_PANEL_ALT};
        border-bottom: 1px solid {Colors.BORDER};
    }}

    QWidget#{scope}[state="confirmed"] {{
        background: rgba(76, 175, 80, 40);
        border-bottom: 1px solid {Colors.SUCCESS};
    }}

    QWidget#{scope}[state="unconfirmed"] {{
        background: rgba(224, 164, 88, 35);
        border-bottom: 1px solid {Colors.WARNING};
    }}

    #{scope} QLabel#confirmationText {{
        color: {Colors.TEXT_PRIMARY};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}

    #{scope} QPushButton#confirmButton {{
        background: {Colors.ACCENT};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 4px 12px;
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}

    #{scope} QPushButton#confirmButton:disabled {{
        background: {Colors.BG_SURFACE};
        color: {Colors.TEXT_DISABLED};
    }}
    """


def slider(scope: str) -> str:
    return f"""
    #{scope} QSlider {{
        min-width: 250px;
        max-width: 500px;
    }}

    #{scope} QSlider::groove:horizontal {{
        height: 5px;
        background: {Colors.BORDER};
        border-radius: 2px;
    }}

    #{scope} QSlider::sub-page:horizontal {{
        background: {Colors.ACCENT_BLUE};
        border-radius: 2px;
    }}

    #{scope} QSlider::add-page:horizontal {{
        background: {Colors.BG_SURFACE};
        border-radius: 2px;
    }}

    #{scope} QSlider::handle:horizontal {{
        width: 13px;
        height: 13px;
        margin: -4px 0;
        background: {Colors.TEXT_MUTED_ALT};
        border: 1px solid {Colors.BORDER_HOVER};
        border-radius: 6px;
    }}

    #{scope} QSlider::handle:horizontal:hover {{
        background: #ffffff;
        border-color: {Colors.ACCENT_BLUE};
    }}
    """


def spinbox(scope: str) -> str:
    return f"""
    #{scope} QSpinBox {{
        background-color: {Colors.BG_SURFACE};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 4px;
        padding: 4px 6px;
        font-size: {Typography.SIZE_XS};
        min-width: 20px;
    }}

    #{scope} QSpinBox:hover {{
        border-color: {Colors.BORDER_HOVER};
    }}

    #{scope} QSpinBox:focus {{
        border-color: {Colors.ACCENT_BLUE};
    }}

    #{scope} QSpinBox::up-button, #{scope} QSpinBox::down-button {{
        background-color: {Colors.BG_SURFACE};
        border: none;
        width: 16px;
    }}

    #{scope} QSpinBox::up-button:hover, #{scope} QSpinBox::down-button:hover {{
        background-color: {Colors.BG_SURFACE_HOVER};
    }}
    """


def layer_row(scope):
    return f"""
    #{scope} QWidget#layerRow {{
        background: transparent;
        border-radius: 8px;
        border-left: 3px solid transparent;
    }}

    #{scope} QWidget#layerRow:hover {{
        background: {Colors.BG_HOVER};
    }}

    #{scope} QWidget#layerRow QPushButton {{
        background: transparent;
        border: none;
        text-align: left;
        padding: 10px 10px 10px 12px;
        color: {Colors.TEXT_PRIMARY};
    }}

    #{scope} QWidget#layerRow QPushButton:hover {{
        background: {Colors.ACCENT};
        color: white;
    }}

    #{scope} QWidget#layerRow[active="true"] {{
        background: {Colors.with_alpha(Colors.ACCENT, 40)};
        border-left: 3px solid {Colors.ACCENT};
    }}

    #{scope} QWidget#layerRow[active="true"] QPushButton {{
        color: {Colors.TEXT_BRIGHT};
        font-weight: bold;
    }}

    #{scope} QWidget#layerRow[active="true"] QPushButton:hover {{
        background: {Colors.ACCENT};
        color: white;
    }}
    """


def video_label_row(scope: str) -> str:
    return f"""
    #{scope} QWidget#videoLabelRow {{
        background: transparent;
        border-radius: 8px;
        border-left: 3px solid transparent;
    }}

    #{scope} QWidget#videoLabelRow:hover {{
        background: {Colors.ACCENT};
    }}

    #{scope} QWidget#videoLabelRow:hover QPushButton {{
        color: white;
    }}

    #{scope} QWidget#videoLabelRow[active="true"] {{
        background: {Colors.with_alpha(Colors.ACCENT, 40)};
        border-left: 3px solid {Colors.ACCENT};
    }}

    #{scope} QWidget#videoLabelRow QPushButton {{
        background: transparent;
        border: none;
        text-align: left;
        padding: 6px 10px 6px 6px;
        color: {Colors.TEXT_PRIMARY};
    }}

    #{scope} QWidget#videoLabelRow[active="true"] QPushButton {{
        color: {Colors.TEXT_BRIGHT};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}
    """


def sidebar_tabs(scope: str) -> str:
    return f"""
    #{scope} QTabWidget {{
        background: transparent;
    }}

    #{scope} QTabWidget::pane {{
        border: none;
        background: transparent;
    }}

    #{scope} QTabBar::tab {{
        background: transparent;
        color: {Colors.TEXT_MUTED};
        border: none;
        padding: 8px 12px;
        margin: 0px;
    }}

    #{scope} QTabBar::tab:hover {{
        background: {Colors.BG_HOVER};
        color: {Colors.TEXT_PRIMARY};
    }}

    #{scope} QTabBar::tab:selected {{
        background: {Colors.ACCENT};
        color: white;
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}
    """
