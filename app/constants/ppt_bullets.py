"""G10X Highlights bullet rules — category headers use ONLY the Wingdings arrowhead."""

# List level for "Stories completed this week" and similar category headers
CATEGORY_HEADER_LEVEL = 7

# G10X stores buChar="Ø" (U+00D8) with buFont="Wingdings,Sans-Serif".
# That combination renders as the solid right-pointing arrowhead (not •, -, or ▶).
CATEGORY_HEADER_BULLET = "\u00d8"
CATEGORY_HEADER_BULLET_FONT = "Wingdings,Sans-Serif"
CATEGORY_HEADER_BULLET_COLOR = "000000"

# Preview label for text output (visual stand-in for the Wingdings arrowhead)
CATEGORY_HEADER_PREVIEW_SYMBOL = "\u25ba"  # ►

# Key Activities list items — round bullet at outline level 0 (all G10X templates)
KA_BULLET_CHAR = "\u2022"  # •
KA_BULLET_LEVEL = 0

# Must NEVER be used for category headers
FORBIDDEN_CATEGORY_HEADER_BULLETS: tuple[str, ...] = (
    "\u2022",  # • round (sprint lines)
    "-",
    "\u208b",  # ₋ dash (story lines)
    "\u2013",  # – en dash
    "\u25b6",  # ▶ black right-pointing triangle (wrong font/glyph)
    "\u25ba",  # ► (wrong unless via Wingdings Ø mapping)
    "\u27a4",  # ➤ heavy arrow
    "\u2192",  # →
    ">",
)


def is_valid_category_header_bullet(
    char: str | None,
    font: str | None,
    level: int | None,
) -> bool:
    """True only for G10X category header: lvl 7 + Ø + Wingdings."""
    if level != CATEGORY_HEADER_LEVEL:
        return False
    if char != CATEGORY_HEADER_BULLET:
        return False
    if not font or "Wingdings" not in font:
        return False
    return True
