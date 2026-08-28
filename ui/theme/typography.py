"""Type scale. Sizes as px strings for direct QSS interpolation."""


class Typography:
    FAMILY = "Arial"

    SIZE_XS = "12px"
    SIZE_SM = "13px"
    SIZE_MD = "14px"
    SIZE_LG = "18px"

    WEIGHT_REGULAR = 500
    WEIGHT_BOLD = 600
    WEIGHT_BOLD_QSS = "bold"  # QSS wants the keyword, QFont wants an int
