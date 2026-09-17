"""
Assembles component fragments into the stylesheet each widget actually applies.
"""

from . import components as c, Typography
from .colors import Colors


def right_sidebar_style(scope: str = "rightSidebar") -> str:
    return "\n".join([
        c.header_label(scope),
        c.surface_button(scope),
        c.status_labels(scope),
        c.detection_row(scope),
        c.icon_button(scope),
        c.default_text(scope),
    ])


def confirmation_bar_style(scope: str = "confirmationBar") -> str:
    return "\n".join([
        c.confirmation_bar(scope),
        c.status_labels(scope),
    ])


def bottom_bar_style(scope: str = "bottomToolbar") -> str:
    return "\n".join([
        f"""
        QWidget#{scope} {{
            background-color: {Colors.BG_SURFACE};
            border-top: 1px solid {Colors.BORDER};
            padding: 5px 10px;
        }}
        """,
        c.surface_button(scope),
        c.navigation_button(scope),
        c.slider(scope),
        c.spinbox(scope),
        c.default_text(scope),
    ])


def temporal_timeline_style(scope: str = "timelineHeader") -> str:
    return "\n".join([
        c.surface_button(scope),
        c.default_text(scope),
    ])


def top_toolbar_style(scope: str = "topToolbar") -> str:
    return "\n".join([
        c.top_toolbar(scope),
    ])


def build_stylesheet() -> str:
    """Full app-wide stylesheet. Applied via ThemeManager on every
    theme switch (and once at startup via load_saved_theme())."""
    return "\n".join([
        left_sidebar_style(),
        right_sidebar_style(),
        bottom_bar_style(),
        temporal_timeline_style(),
        top_toolbar_style(),
        c.tooltip(),
    ])


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
        padding: 8px 12px;
        border: none;
    }}

    #{scope} QTabBar::tab:hover {{
        color: {Colors.TEXT_PRIMARY};
        background: {Colors.BG_HOVER};
    }}

    #{scope} QTabBar::tab:selected {{
        color: {Colors.TEXT_BRIGHT};
        background: {Colors.ACCENT};
        font-weight: {Typography.WEIGHT_BOLD_QSS};
    }}
    """


def left_sidebar_style(scope: str = "leftSidebar") -> str:
    return "\n".join([
        c.panel_base(scope),
        c.section_title(scope),
        c.separator(scope),
        c.nav_row_button(scope),
        c.label_button(scope),
        c.tool_toggle_button(scope),
        c.icon_toolbutton(scope),
        c.layer_row(scope),
        c.video_label_row(scope),
        c.sidebar_tabs(scope),
        c.default_text(scope),
        c.tooltip(),
    ])

