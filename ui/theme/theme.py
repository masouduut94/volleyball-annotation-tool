"""
Assembles component fragments into the stylesheet each widget actually applies.

Two ways to use this:

1. Per-widget (least invasive, good for migrating incrementally):
       self.setObjectName("leftSidebar")
       self.setStyleSheet(left_sidebar_style())

2. App-wide (recommended once everything has an objectName):
       app.setStyleSheet(build_stylesheet())
   and remove every individual setStyleSheet() call. One QSS document,
   no per-widget calls, no risk of one widget's rules clobbering another's.
"""

from . import components as c


def left_sidebar_style(scope: str = "leftSidebar") -> str:
    return "\n".join([
        c.panel_base(scope),
        c.section_title(scope),
        c.separator(scope),
        c.nav_row_button(scope),
        c.label_button(scope),
        c.tool_toggle_button(scope),
        c.icon_toolbutton(scope),
        c.tooltip(),
    ])


def right_sidebar_style(scope: str = "rightSidebar") -> str:
    return "\n".join([
        c.header_label(scope),
        c.surface_button(scope),
        c.status_labels(scope),
    ])


def bottom_bar_style(scope: str = "bottomToolbar") -> str:
    return "\n".join([
        f"""
        QWidget#{scope} {{
            background-color: #2b2b2b;
            border-top: 1px solid #3c3c3c;
            padding: 5px 10px;
        }}
        """,
        c.surface_button(scope),
        c.slider(scope),
        c.spinbox(scope),
    ])


def build_stylesheet() -> str:
    """Full app-wide stylesheet. Apply once via app.setStyleSheet(...)."""
    return "\n".join([
        left_sidebar_style(),
        right_sidebar_style(),
        bottom_bar_style(),
        c.tooltip(),
    ])
