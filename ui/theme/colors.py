"""
Central color palette.

Every color used anywhere in the app should come from here.
If you need a new color, add it here first — never inline a hex value
in a widget file again.
"""


class Colors:
    # Backgrounds
    BG_APP = "#1E1F24"
    BG_PANEL_ALT = "#1E2229"
    BG_SURFACE = "#2C313A"
    BG_SURFACE_HOVER = "#353B46"
    BG_SURFACE_PRESSED = "#252A32"
    BG_HOVER = "#323540"
    BG_HOVER_ALT = "#383C47"

    # Borders / lines
    BORDER = "#3A3F4B"
    BORDER_HOVER = "#4A5260"
    LINE = "#2A2D34"
    DIVIDER = "#343A45"

    # Brand / accent
    ACCENT = "#E95420"

    # Text
    TEXT_PRIMARY = "#E6E6E6"
    TEXT_BRIGHT = "#F1F3F5"
    TEXT_HEADER = "#F2F2F2"
    TEXT_MUTED = "#9AA0A6"
    TEXT_MUTED_ALT = "#AEB4BE"
    TEXT_DIM = "#888888"
    TEXT_DISABLED = "#666666"

    # Status
    SUCCESS = "#4CAF50"
    WARNING = "#E0A458"

    # Slider / misc accents
    ACCENT_BLUE = "#4a90d9"

    # Tooltip (light, intentionally off-theme)
    TOOLTIP_BG = "#FFF8C6"
    TOOLTIP_BORDER = "#C9B458"
    TOOLTIP_TEXT = "#202020"
