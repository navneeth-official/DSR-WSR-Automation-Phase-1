"""HL internal waste helpers shared by layout violation detectors."""

from __future__ import annotations

from typing import Any

from app.constants.evaluation_ground_truth import CONTAINER_WASTE_REPORT_MIN_IN
from app.services.template_calibration import TemplateLayoutThresholds


def _is_contd_hl_slide(slide: dict[str, Any]) -> bool:
    return bool(slide.get("is_contd") and slide.get("highlights"))


def _is_hl_dense_fill(hl: dict[str, Any], thresholds: TemplateLayoutThresholds) -> bool:
    util = hl.get("effective_utilization_ratio", hl.get("utilization_ratio"))
    if util is None:
        return False
    return float(util) >= thresholds.hl_dense_fill_min_effective_util


def hl_bottom_waste_in(slide: dict[str, Any]) -> float | None:
    """Empty inches below HL content (max of measured below-text and box slack)."""
    below = slide.get("hl_waste_below_text_in")
    box_unused = slide.get("hl_box_unused_in")
    if below is None and box_unused is None:
        return None
    return round(max(float(below or 0), float(box_unused or 0)), 4)


def hl_waste_limit(slide: dict[str, Any], thresholds: TemplateLayoutThresholds) -> float:
    """
    Calibrated internal-waste band from measured layout, not slide labels.

    Dense-fill slides (high effective utilization) use a tight band.
    Sparse HL with a Key Activities section uses the wider template band.
    Continuation HL slides use the relaxed contd band.
    """
    if _is_contd_hl_slide(slide):
        return thresholds.hl_waste_contd_hl_max_in
    hl = slide.get("highlights") or {}
    if _is_hl_dense_fill(hl, thresholds):
        return thresholds.hl_waste_dense_fill_max_in
    if slide.get("key_activities") is not None:
        return thresholds.hl_waste_sparse_ka_max_in
    return thresholds.hl_waste_dense_fill_max_in


def container_waste_report_limit(template_limit_in: float) -> float:
    """Effective inch threshold before container waste is surfaced in validation."""
    return max(float(template_limit_in), CONTAINER_WASTE_REPORT_MIN_IN)


def should_report_container_waste(
    waste_in: float | None,
    template_limit_in: float,
) -> bool:
    """True only when slack exceeds the larger of template band and report floor."""
    if waste_in is None:
        return False
    return float(waste_in) > container_waste_report_limit(template_limit_in)
