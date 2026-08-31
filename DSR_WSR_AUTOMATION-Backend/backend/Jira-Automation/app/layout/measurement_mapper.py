"""
Map vision JSON measurements to deterministic EMU correction deltas.

This module is the single integration point between parsed vision output
(``SlideMeasurements`` / issue ``measurement`` dicts) and ``LayoutCorrector``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.layout.config import LayoutCorrectorConfig
from app.layout.shape_ops import PixelScale
from app.vision.types import SlideMeasurements

# Canonical slide-level measurement keys from the vision prompt schema.
SLIDE_MEASUREMENT_KEYS = (
    "highlight_box_top",
    "highlight_box_bottom",
    "last_highlight_text_bottom",
    "unused_space_inside_highlight",
    "keyactivities_title_top",
    "keyactivities_box_top",
    "keyactivities_box_bottom",
    "gap_between_sections",
)

# Issue-level measurement keys observed in model output (with aliases).
ISSUE_GAP_KEYS = ("gap_pixels", "gap_between_sections")
ISSUE_OVERLAP_KEYS = ("overlap_pixels",)
ISSUE_UNUSED_KEYS = (
    "unused_space_pixels",
    "unused_pixels",
    "waste_pixels",
    "unused_space_inside_highlight",
)
ISSUE_OVERFLOW_KEYS = ("overflow_pixels", "missing_pixels")


@dataclass(frozen=True)
class VisionFieldMapping:
    """Documents how a vision field flows into layout correction."""

    vision_field: str
    parsed_in: str
    consumer: str
    ppt_modification: str
    value_source: str  # "measured" | "computed" | "fallback" | "unused"


VISION_FIELD_MAPPINGS: tuple[VisionFieldMapping, ...] = (
    VisionFieldMapping(
        vision_field="measurements.gap_between_sections",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="VisionMeasurementMapper.gap_deficit_emu / gap_excess_emu",
        ppt_modification="Move Key Activities down (gap too small) or up (excess gap issue)",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="measurements.unused_space_inside_highlight",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="VisionMeasurementMapper.hl_shrink_excess_emu / hl_shrink_to_remove_emu",
        ppt_modification="Shrink Highlights table height",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="measurements.last_highlight_text_bottom",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="VisionMeasurementMapper.upper_content_bottom_px",
        ppt_modification="Anchor for gap / overlap computation and maintain_gap upper bound",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="measurements.highlight_box_bottom",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="VisionMeasurementMapper.upper_content_bottom_px / hl_expand_emu",
        ppt_modification="Fallback upper bound; overflow extent when text exceeds box",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="measurements.highlight_box_top",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="(none — informational only)",
        ppt_modification="Not applied",
        value_source="unused",
    ),
    VisionFieldMapping(
        vision_field="measurements.keyactivities_title_top",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="VisionMeasurementMapper.ka_section_top_px / gap_px",
        ppt_modification="Derives section gap and overlap when gap_between_sections absent",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="measurements.keyactivities_box_top",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="VisionMeasurementMapper.ka_section_top_px / gap_px",
        ppt_modification="Fallback KA top for gap / overlap computation",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="measurements.keyactivities_box_bottom",
        parsed_in="app/vision/parser.py::_parse_measurements",
        consumer="(none — no existing correction rule)",
        ppt_modification="Not applied",
        value_source="unused",
    ),
    VisionFieldMapping(
        vision_field="issues[].measurement.gap_pixels",
        parsed_in="app/vision/parser.py::_parse_issue",
        consumer="VisionMeasurementMapper.gap_excess_emu (move_section_up)",
        ppt_modification="Move Key Activities up by excess over min clearance",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="issues[].measurement.overlap_pixels",
        parsed_in="app/vision/parser.py::_parse_issue",
        consumer="VisionMeasurementMapper.overlap_emu (move_section_down)",
        ppt_modification="Move Key Activities down",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="issues[].measurement.unused_space_pixels",
        parsed_in="app/vision/parser.py::_parse_issue",
        consumer="VisionMeasurementMapper.hl_shrink_to_remove_emu",
        ppt_modification="Shrink Highlights by measured unused space",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="issues[].measurement.overflow_pixels",
        parsed_in="app/vision/parser.py::_parse_issue",
        consumer="VisionMeasurementMapper.hl_expand_emu",
        ppt_modification="Expand Highlights table height",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="issues[].measurement.missing_pixels",
        parsed_in="app/vision/parser.py::_parse_issue",
        consumer="VisionMeasurementMapper.hl_expand_emu",
        ppt_modification="Expand Highlights table height",
        value_source="measured",
    ),
    VisionFieldMapping(
        vision_field="issues[].recommended_action",
        parsed_in="app/vision/parser.py::_parse_issue",
        consumer="LayoutCorrector._apply_issue_action",
        ppt_modification="Selects which mapper method / shape op runs",
        value_source="measured",
    ),
)


def _values_dict(
    measurements: SlideMeasurements | Mapping[str, Any] | None,
) -> dict[str, int | float]:
    if measurements is None:
        return {}
    if isinstance(measurements, SlideMeasurements):
        return dict(measurements.values)
    return dict(measurements)


def first_px(
    *sources: Mapping[str, Any] | None,
    keys: tuple[str, ...],
) -> float | None:
    """Return the first numeric value found across sources for any of ``keys``."""
    for source in sources:
        if not source:
            continue
        for key in keys:
            raw = source.get(key)
            if isinstance(raw, (int, float)):
                return float(raw)
    return None


class VisionMeasurementMapper:
    """Convert vision pixel measurements into slide EMU correction deltas."""

    def __init__(self, scale: PixelScale, config: LayoutCorrectorConfig | None = None) -> None:
        self._scale = scale
        self._config = config or LayoutCorrectorConfig()

    @property
    def min_gap_emu(self) -> int:
        return self._config.min_text_ka_clearance_emu

    @property
    def max_waste_emu(self) -> int:
        return self._config.max_hl_unused_space_emu

    @property
    def min_gap_px(self) -> float:
        return self._scale.emu_y_to_px(self.min_gap_emu)

    @property
    def max_waste_px(self) -> float:
        return self._scale.emu_y_to_px(self.max_waste_emu)

    def px_to_emu_y(self, px: float) -> int:
        return self._scale.px_y_to_emu(px)

    def upper_content_bottom_px(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
    ) -> float | None:
        values = _values_dict(slide_measurements)
        return first_px(
            values,
            keys=("last_highlight_text_bottom", "highlight_box_bottom"),
        )

    def upper_content_bottom_emu(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
    ) -> int | None:
        px = self.upper_content_bottom_px(slide_measurements)
        if px is None:
            return None
        return self.px_to_emu_y(px)

    def ka_section_top_px(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
    ) -> float | None:
        values = _values_dict(slide_measurements)
        return first_px(
            values,
            keys=("keyactivities_title_top", "keyactivities_box_top"),
        )

    def gap_px(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> float | None:
        """Section gap in image pixels (KA top minus HL text/box bottom)."""
        direct = first_px(
            issue_measurement,
            _values_dict(slide_measurements),
            keys=ISSUE_GAP_KEYS,
        )
        if direct is not None:
            return direct
        upper = self.upper_content_bottom_px(slide_measurements)
        ka_top = self.ka_section_top_px(slide_measurements)
        if upper is None or ka_top is None:
            return None
        return ka_top - upper

    def gap_deficit_emu(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
    ) -> int | None:
        """
        EMU to move Key Activities down when the measured gap is below minimum.

        Returns ``None`` when gap is adequate or cannot be determined.
        """
        gap_px = self.gap_px(slide_measurements)
        if gap_px is None:
            return None
        gap_emu = self.px_to_emu_y(gap_px)
        if gap_emu < self.min_gap_emu:
            return self.min_gap_emu - gap_emu
        return None

    def gap_excess_emu(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> int | None:
        """
        EMU to move Key Activities up when the measured gap exceeds minimum.

        Returns a positive magnitude; callers apply as negative top delta.
        """
        gap_px = self.gap_px(slide_measurements, issue_measurement)
        if gap_px is None:
            return None
        gap_emu = self.px_to_emu_y(gap_px)
        if gap_emu > self.min_gap_emu:
            return gap_emu - self.min_gap_emu
        return None

    def overlap_px(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> float | None:
        """
        Overlap between Highlights content and Key Activities in pixels.

        Uses ``overlap_pixels`` from the issue when present; otherwise derives
        overlap from slide measurements and minimum clearance.
        """
        issue_overlap = first_px(issue_measurement, keys=ISSUE_OVERLAP_KEYS)
        if issue_overlap is not None:
            return max(0.0, issue_overlap)

        upper = self.upper_content_bottom_px(slide_measurements)
        ka_top = self.ka_section_top_px(slide_measurements)
        if upper is None or ka_top is None:
            return None
        required_ka_top = upper + self.min_gap_px
        if ka_top < required_ka_top:
            return required_ka_top - ka_top
        return 0.0

    def overlap_emu(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> int | None:
        px = self.overlap_px(slide_measurements, issue_measurement)
        if px is None:
            return None
        if px <= 0:
            return None
        return self.px_to_emu_y(px)

    def unused_space_px(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> float | None:
        return first_px(
            issue_measurement,
            _values_dict(slide_measurements),
            keys=ISSUE_UNUSED_KEYS,
        )

    def hl_shrink_excess_emu(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> int | None:
        """
        EMU to shrink Highlights when measured waste exceeds configured tolerance.

        Used by slide-level measurement rules (threshold-driven).
        """
        waste_px = self.unused_space_px(slide_measurements, issue_measurement)
        if waste_px is None:
            return None
        waste_emu = self.px_to_emu_y(waste_px)
        if waste_emu <= self.max_waste_emu:
            return None
        return waste_emu - self.max_waste_emu

    def hl_shrink_to_remove_emu(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> int | None:
        """
        EMU to shrink Highlights by the full measured unused space.

        Used when vision explicitly recommends ``reduce_unused_space`` or
        ``decrease_textbox_height``.
        """
        waste_px = self.unused_space_px(slide_measurements, issue_measurement)
        if waste_px is None or waste_px <= 0:
            return None
        return self.px_to_emu_y(waste_px)

    def hl_expand_emu(
        self,
        slide_measurements: SlideMeasurements | Mapping[str, Any] | None,
        issue_measurement: Mapping[str, Any] | None = None,
    ) -> int | None:
        """EMU to expand Highlights when overflow is measured or derivable."""
        overflow_px = first_px(issue_measurement, keys=ISSUE_OVERFLOW_KEYS)
        if overflow_px is not None and overflow_px > 0:
            return self.px_to_emu_y(overflow_px)

        values = _values_dict(slide_measurements)
        last_text = values.get("last_highlight_text_bottom")
        hl_bottom = values.get("highlight_box_bottom")
        if isinstance(last_text, (int, float)) and isinstance(hl_bottom, (int, float)):
            if last_text > hl_bottom:
                return self.px_to_emu_y(float(last_text - hl_bottom))

        # overlap_pixels on expand actions indicates text spilling into KA region
        spill_px = first_px(issue_measurement, keys=ISSUE_OVERLAP_KEYS)
        if spill_px is not None and spill_px > 0:
            return self.px_to_emu_y(spill_px)

        return None
