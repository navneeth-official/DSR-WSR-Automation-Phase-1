"""Layout correction configuration (thresholds derived from shared metrics)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ppt_layout_metrics import (
    EMU_PER_INCH,
    FOOTER_MAX_BOTTOM_IN,
    MIN_TEXT_KA_CLEARANCE_IN,
    SPARSE_HL_MAX_WASTE_IN,
)


@dataclass(frozen=True)
class LayoutCorrectorConfig:
    """Tolerances for vision-driven deterministic corrections."""

    min_text_ka_clearance_in: float = MIN_TEXT_KA_CLEARANCE_IN
    max_hl_unused_space_in: float = SPARSE_HL_MAX_WASTE_IN
    footer_max_bottom_in: float = FOOTER_MAX_BOTTOM_IN
    default_image_width_px: int = 1920
    default_image_height_px: int = 1080

    @property
    def min_text_ka_clearance_emu(self) -> int:
        return int(self.min_text_ka_clearance_in * EMU_PER_INCH)

    @property
    def max_hl_unused_space_emu(self) -> int:
        return int(self.max_hl_unused_space_in * EMU_PER_INCH)

    @property
    def footer_max_bottom_emu(self) -> int:
        return int(self.footer_max_bottom_in * EMU_PER_INCH)
