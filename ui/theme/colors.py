"""
Central color palette.

Every color used anywhere in the app should come from here — never
inline a hex value in a widget file.

Colors is a plain class with class-level attributes on purpose: every
existing component in components.py reads it as `Colors.BG_APP`,
`Colors.TEXT_PRIMARY`, etc., evaluated at the moment each `xyz_style()`
function actually RUNS — not bound at import time. That means swapping
the values on this class via apply() and regenerating the stylesheet is
enough to re-theme the whole app without touching components.py at all.

Defaults below are the dark theme, so anything reading Colors.* before a
theme is explicitly applied still gets a fully-defined palette.
"""

from .palettes import DARK_PALETTE


class Colors:
    BG_APP = DARK_PALETTE["BG_APP"]
    BG_PANEL_ALT = DARK_PALETTE["BG_PANEL_ALT"]
    BG_SURFACE = DARK_PALETTE["BG_SURFACE"]
    BG_SURFACE_HOVER = DARK_PALETTE["BG_SURFACE_HOVER"]
    BG_SURFACE_PRESSED = DARK_PALETTE["BG_SURFACE_PRESSED"]
    BG_HOVER = DARK_PALETTE["BG_HOVER"]
    BG_HOVER_ALT = DARK_PALETTE["BG_HOVER_ALT"]

    BORDER = DARK_PALETTE["BORDER"]
    BORDER_HOVER = DARK_PALETTE["BORDER_HOVER"]
    LINE = DARK_PALETTE["LINE"]
    DIVIDER = DARK_PALETTE["DIVIDER"]

    ACCENT = DARK_PALETTE["ACCENT"]

    TEXT_PRIMARY = DARK_PALETTE["TEXT_PRIMARY"]
    TEXT_BRIGHT = DARK_PALETTE["TEXT_BRIGHT"]
    TEXT_HEADER = DARK_PALETTE["TEXT_HEADER"]
    TEXT_MUTED = DARK_PALETTE["TEXT_MUTED"]
    TEXT_MUTED_ALT = DARK_PALETTE["TEXT_MUTED_ALT"]
    TEXT_DIM = DARK_PALETTE["TEXT_DIM"]
    TEXT_DISABLED = DARK_PALETTE["TEXT_DISABLED"]

    SUCCESS = DARK_PALETTE["SUCCESS"]
    WARNING = DARK_PALETTE["WARNING"]

    ACCENT_BLUE = DARK_PALETTE["ACCENT_BLUE"]

    TOOLTIP_BG = DARK_PALETTE["TOOLTIP_BG"]
    TOOLTIP_BORDER = DARK_PALETTE["TOOLTIP_BORDER"]
    TOOLTIP_TEXT = DARK_PALETTE["TOOLTIP_TEXT"]

    @classmethod
    def apply(cls, palette: dict):
        """
        Overwrite every attribute above from `palette` (see palettes.py).
        Called exclusively by ThemeManager — mutating Colors alone does
        nothing visible until the stylesheet is regenerated and
        re-applied, which ThemeManager does immediately afterward.
        """
        for key, value in palette.items():
            setattr(cls, key, value)


    @staticmethod
    def with_alpha(hex_color: str, alpha: int) -> str:
        """rgba(...) string for a #RRGGBB color at 0-255 alpha — used for
        subtle tinted highlights instead of a hardcoded flat fill."""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"