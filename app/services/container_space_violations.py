"""Detect unused space inside Highlights and Key Activities containers."""

from __future__ import annotations

from typing import Any

from app.services.hl_waste_limits import (
    container_waste_report_limit,
    hl_bottom_waste_in,
    hl_waste_limit,
    should_report_container_waste,
)
from app.services.template_calibration import TemplateLayoutThresholds


def _combined_waste(slide: dict[str, Any], prefix: str) -> float:
    above = slide.get(f"{prefix}_waste_above_text_in") or 0.0
    below = slide.get(f"{prefix}_waste_below_text_in") or 0.0
    if prefix == "hl":
        below = max(float(below), float(slide.get("hl_box_unused_in") or 0))
    elif prefix == "ka":
        below = max(float(below), float(slide.get("ka_box_unused_in") or 0))
    return round(float(above) + float(below), 4)


def detect_container_space_violations(
    slide: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds,
) -> list[dict[str, Any]]:
    """Flag top/bottom slack and under-utilized HL/KA boxes."""
    violations: list[dict[str, Any]] = []
    idx = slide.get("slide_index")
    title = slide.get("title", "")
    hl = slide.get("highlights")

    if hl:
        top_waste = slide.get("hl_waste_above_text_in")
        top_limit = thresholds.hl_waste_above_text_max_in
        if should_report_container_waste(top_waste, top_limit):
            violations.append(
                {
                    "rule_id": "HL-TOP-WASTE-01",
                    "severity": "minor",
                    "slide_index": idx,
                    "title": title,
                    "target": "highlights",
                    "waste_region": "top",
                    "message": (
                        "Highlights tab has unused empty space at the top "
                        f"({float(top_waste):.2f} in). Move content up or shrink the box."
                    ),
                    "hl_waste_above_text_in": top_waste,
                    "limit_in": container_waste_report_limit(top_limit),
                }
            )

        bottom_waste = hl_bottom_waste_in(slide)
        bottom_template_limit = hl_waste_limit(slide, thresholds)
        if should_report_container_waste(bottom_waste, bottom_template_limit):
            report_limit = container_waste_report_limit(bottom_template_limit)
            violations.append(
                {
                    "rule_id": "HL-BOTTOM-WASTE-01",
                    "severity": "minor",
                    "slide_index": idx,
                    "title": title,
                    "target": "highlights",
                    "waste_region": "bottom",
                    "message": (
                        "Highlights tab has unused empty space at the bottom "
                        f"({float(bottom_waste):.2f} in, report limit {report_limit:.2f} in). "
                        "Shrink the Highlights table to fit the content."
                    ),
                    "hl_waste_below_text_in": bottom_waste,
                    "hl_waste_in": bottom_waste,
                    "hl_box_unused_in": slide.get("hl_box_unused_in"),
                    "limit_in": report_limit,
                }
            )

        util = hl.get("effective_utilization_ratio", hl.get("utilization_ratio"))
        _ = util  # under-utilization is covered by HL-BOTTOM-WASTE-01 on the same slide

    ka = slide.get("key_activities")
    if ka:
        ka_top = slide.get("ka_waste_above_text_in")
        ka_top_limit = thresholds.ka_waste_above_text_max_in
        if should_report_container_waste(ka_top, ka_top_limit):
            violations.append(
                {
                    "rule_id": "KA-TOP-WASTE-01",
                    "severity": "minor",
                    "slide_index": idx,
                    "title": title,
                    "target": "key_activities",
                    "waste_region": "top",
                    "message": (
                        "Key Activities tab has unused empty space at the top "
                        f"({float(ka_top):.2f} in). Move items up or shrink the box."
                    ),
                    "ka_waste_above_text_in": ka_top,
                    "limit_in": container_waste_report_limit(ka_top_limit),
                }
            )

        ka_bottom = slide.get("ka_waste_below_text_in")
        ka_box_unused = slide.get("ka_box_unused_in")
        if ka_box_unused is not None:
            ka_bottom = max(float(ka_bottom or 0), float(ka_box_unused))
        ka_bottom_limit = thresholds.ka_waste_below_text_max_in
        item_count = ka.get("item_count") or 0
        if item_count > 0 and should_report_container_waste(ka_bottom, ka_bottom_limit):
            report_limit = container_waste_report_limit(ka_bottom_limit)
            violations.append(
                {
                    "rule_id": "KA-BOTTOM-WASTE-01",
                    "severity": "minor",
                    "slide_index": idx,
                    "title": title,
                    "target": "key_activities",
                    "waste_region": "bottom",
                    "message": (
                        "Key Activities tab has unused empty space at the bottom "
                        f"({float(ka_bottom):.2f} in, report limit {report_limit:.2f} in). "
                        "Shrink the Key Activities table to fit the items."
                    ),
                    "ka_waste_below_text_in": ka_bottom,
                    "limit_in": report_limit,
                }
            )

        ka_util = ka.get("utilization_ratio")
        ka_combined = _combined_waste(slide, "ka")
        if (
            item_count > 0
            and ka_util is not None
            and float(ka_util) < thresholds.container_underutilization_max_util
            and ka_combined >= thresholds.container_combined_waste_min_in
        ):
            violations.append(
                {
                    "rule_id": "KA-UTIL-01",
                    "severity": "minor",
                    "slide_index": idx,
                    "title": title,
                    "target": "key_activities",
                    "message": (
                        "Key Activities tab is not efficiently used "
                        f"({float(ka_util):.0%} fill, {ka_combined:.2f} in combined empty space). "
                        "Resize the Key Activities table to match the items."
                    ),
                    "utilization_ratio": ka_util,
                    "combined_waste_in": ka_combined,
                }
            )

    return violations
