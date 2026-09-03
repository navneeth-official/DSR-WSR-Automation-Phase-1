"""G10X Highlights bullet rules — category headers use ONLY the Wingdings arrowhead."""

from __future__ import annotations

from dataclasses import dataclass

# Legacy Sustainment template: list level 7 + buChar U+00D8
CATEGORY_HEADER_LEVEL = 7

# G10X stores buChar="Ø" (U+00D8) with buFont="Wingdings,Sans-Serif".
# Generic/Haskell templates often use list level 1 + buChar U+F0D8 — same glyph.
CATEGORY_HEADER_BULLET = "\u00d8"
CATEGORY_HEADER_BULLET_FONT = "Wingdings,Sans-Serif"
CATEGORY_HEADER_BULLET_COLOR = "000000"

# Accepted encodings across WSR templates (same rendered arrowhead).
CATEGORY_HEADER_LEVELS = frozenset({1, 7})
CATEGORY_HEADER_BULLET_CHARS = frozenset({"\u00d8", "\uf0d8"})

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


@dataclass(frozen=True)
class CategoryBulletSpec:
    """Category-header bullet shape observed in a reference template."""

    levels: frozenset[int]
    bullet_chars: frozenset[str]
    bullet_fonts: frozenset[str] = frozenset()

    def matches(
        self,
        char: str | None,
        font: str | None,
        level: int | None,
    ) -> bool:
        if level is None or int(level) not in self.levels:
            return False
        if char not in self.bullet_chars:
            return False
        if not self.bullet_fonts:
            return True
        if not font:
            return False
        font_low = font.lower()
        for allowed in self.bullet_fonts:
            allowed_low = allowed.lower()
            if allowed_low in font_low or font_low.startswith(allowed_low.split(",")[0]):
                return True
        return False

    def describe(self) -> str:
        levels = ", ".join(str(v) for v in sorted(self.levels))
        fonts = ", ".join(sorted(self.bullet_fonts)) if self.bullet_fonts else "template font"
        return f"level {levels}, bullet {sorted(self.bullet_chars)}, font {fonts}"


def default_category_bullet_spec() -> CategoryBulletSpec:
    """Fallback when no template scan is available."""
    return CategoryBulletSpec(
        levels=CATEGORY_HEADER_LEVELS,
        bullet_chars=CATEGORY_HEADER_BULLET_CHARS,
    )


def is_valid_category_header_bullet(
    char: str | None,
    font: str | None,
    level: int | None,
    *,
    spec: CategoryBulletSpec | None = None,
) -> bool:
    """True when category header bullet matches the reference template."""
    if spec is None:
        return True
    return spec.matches(char, font, level)
