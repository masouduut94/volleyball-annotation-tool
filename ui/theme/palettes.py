"""
Flat color dicts consumed by Colors.apply(). Keys MUST exactly match
every attribute name on the Colors class in colors.py — ThemeManager
doesn't validate this at runtime, so a typo here silently leaves the old
value in place for that one key.
"""

DARK_PALETTE = {
    "BG_APP": "#1E1F24",
    "BG_PANEL_ALT": "#1E2229",
    "BG_SURFACE": "#2C313A",
    "BG_SURFACE_HOVER": "#353B46",
    "BG_SURFACE_PRESSED": "#252A32",
    "BG_HOVER": "#323540",
    "BG_HOVER_ALT": "#383C47",

    "BORDER": "#3A3F4B",
    "BORDER_HOVER": "#4A5260",
    "LINE": "#2A2D34",
    "DIVIDER": "#343A45",

    "ACCENT": "#E95420",

    "TEXT_PRIMARY": "#E6E6E6",
    "TEXT_BRIGHT": "#F1F3F5",
    "TEXT_HEADER": "#F2F2F2",
    "TEXT_MUTED": "#9AA0A6",
    "TEXT_MUTED_ALT": "#AEB4BE",
    "TEXT_DIM": "#888888",
    "TEXT_DISABLED": "#666666",

    "SUCCESS": "#4CAF50",
    "WARNING": "#E0A458",

    "ACCENT_BLUE": "#4a90d9",

    "TOOLTIP_BG": "#FFF8C6",
    "TOOLTIP_BORDER": "#C9B458",
    "TOOLTIP_TEXT": "#202020",
}

LIGHT_PALETTE = {
    "BG_APP": "#F4F5F7",
    "BG_PANEL_ALT": "#FFFFFF",
    "BG_SURFACE": "#FFFFFF",
    "BG_SURFACE_HOVER": "#EEF0F3",
    "BG_SURFACE_PRESSED": "#E2E5E9",
    "BG_HOVER": "#EBEDF0",
    "BG_HOVER_ALT": "#E1E4E8",

    "BORDER": "#D6D9DE",
    "BORDER_HOVER": "#C0C4CC",
    "LINE": "#E2E4E8",
    "DIVIDER": "#DADDE2",

    "ACCENT": "#D9490F",  # deepened vs. dark-mode accent for AA contrast on white

    "TEXT_PRIMARY": "#20242B",
    "TEXT_BRIGHT": "#0C0E11",
    "TEXT_HEADER": "#14171C",
    "TEXT_MUTED": "#5B626C",
    "TEXT_MUTED_ALT": "#6B7480",
    "TEXT_DIM": "#767C86",
    "TEXT_DISABLED": "#A6ABB3",

    "SUCCESS": "#2E7D32",
    "WARNING": "#B15C00",

    "ACCENT_BLUE": "#2F6FB0",

    # Tooltip is intentionally identical in both themes — see the
    # original comment on components.tooltip(): a consistently-colored
    # tooltip reads as its own distinct UI layer regardless of theme.
    "TOOLTIP_BG": "#FFF8C6",
    "TOOLTIP_BORDER": "#C9B458",
    "TOOLTIP_TEXT": "#202020",
}

PALETTES = {"dark": DARK_PALETTE, "light": LIGHT_PALETTE}