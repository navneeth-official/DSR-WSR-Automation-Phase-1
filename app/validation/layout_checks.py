"""Supplemental layout checks for production validation."""

from __future__ import annotations

from typing import Any

from app.services.hl_waste_limits import (
    container_waste_report_limit,
    hl_bottom_waste_in,
    hl_waste_limit,
)
from app.services.ppt_format_violations import _hl_internal_waste_excessive
from app.services.template_calibration import TemplateLayoutThresholds


def detect_supplemental_layout_violations(
    slide: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds,
    existing_rule_ids: set[str],
) -> list[dict[str, Any]]:
    """Add HL waste checks not always emitted by detect_slide_violations."""
    violations: list[dict[str, Any]] = []
    idx = slide.get("slide_index")
    title = slide.get("title", "")
    hl = slide.get("highlights")
    if not hl:
        return violations

    waste_rules = {"HL-WASTE-01", "HL-BOTTOM-WASTE-01", "CONT-HL-01", "CONT-SPARSE-01", "HL-SIZE-01"}
    if waste_rules.isdisjoint(existing_rule_ids) and _hl_internal_waste_excessive(
        slide, thresholds
    ):
        waste = hl_bottom_waste_in(slide)
        limit = container_waste_report_limit(hl_waste_limit(slide, thresholds))
        violations.append(
            {
                "rule_id": "HL-WASTE-01",
                "severity": "critical",
                "slide_index": idx,
                "title": title,
                "message": (
                    "Highlights box has excessive empty space below the text"
                    + (f" ({waste} in empty, template limit {limit} in)" if waste is not None else "")
                ),
                "hl_waste_below_text_in": waste,
                "hl_waste_in": waste,
                "limit_in": limit,
            }
        )

    return violations
