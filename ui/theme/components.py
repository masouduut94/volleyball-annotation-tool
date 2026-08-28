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
        color: #D8DADF;
    }}

    #{scope} QPushButton#labelButton:hover {{
        background: {Colors.BG_HOVER};
    }}

    #{scope} QPushButton#activeLabel {{
        background: {Colors.BG_SURFACE};
        border: 1px solid {Colors.ACCENT};
        border-radius: 8px;
        color: white;
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
    #{scope} QToolButton {{
        background: transparent;
        border: none;
        color: {Colors.TEXT_MUTED};
        padding: 4px;
    }}

    #{scope} QToolButton:hover {{
        color: white;
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


def slider(scope: str) -> str:
    return f"""
    #{scope} QSlider {{
        min-width: 250px;
        max-width: 500px;
    }}

    #{scope} QSlider::groove:horizontal {{
        height: 5px;
        background: #444;
        border-radius: 2px;
    }}

    #{scope} QSlider::sub-page:horizontal {{
        background: {Colors.ACCENT_BLUE};
        border-radius: 2px;
    }}

    #{scope} QSlider::add-page:horizontal {{
        background: #383838;
        border-radius: 2px;
    }}

    #{scope} QSlider::handle:horizontal {{
        width: 13px;
        height: 13px;
        margin: -4px 0;
        background: #d0d0d0;
        border: 1px solid #777;
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
        background-color: #3c3c3c;
        color: #e0e0e0;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 4px 6px;
        font-size: {Typography.SIZE_XS};
        min-width: 20px;
    }}

    #{scope} QSpinBox:hover {{
        border-color: #666;
    }}

    #{scope} QSpinBox:focus {{
        border-color: {Colors.ACCENT_BLUE};
    }}

    #{scope} QSpinBox::up-button, #{scope} QSpinBox::down-button {{
        background-color: #3c3c3c;
        border: none;
        width: 16px;
    }}

    #{scope} QSpinBox::up-button:hover, #{scope} QSpinBox::down-button:hover {{
        background-color: #4a4a4a;
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
