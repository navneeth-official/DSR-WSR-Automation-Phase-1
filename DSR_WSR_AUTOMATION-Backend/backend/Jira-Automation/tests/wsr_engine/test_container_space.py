"""Tests for HL/KA container unused-space detection."""

from __future__ import annotations

from app.constants.evaluation_ground_truth import CONTAINER_WASTE_REPORT_MIN_IN
from app.services.container_space_violations import detect_container_space_violations
from app.services.hl_waste_limits import should_report_container_waste
from app.services.template_calibration import TemplateLayoutThresholds


def test_small_bottom_waste_below_report_floor_is_silent() -> None:
    thresholds = TemplateLayoutThresholds(
        hl_waste_above_text_max_in=0.15,
        hl_waste_dense_fill_max_in=0.60,
        hl_dense_fill_min_effective_util=0.55,
        container_underutilization_max_util=0.55,
    )
    slide = {
        "slide_index": 5,
        "title": "Delivery Status – Test",
        "highlights": {
            "effective_utilization_ratio": 0.25,
            "utilization_ratio": 0.25,
        },
        "hl_waste_below_text_in": 1.44,
        "hl_box_unused_in": 1.44,
    }
    violations = detect_container_space_violations(slide, thresholds=thresholds)
    rule_ids = {v["rule_id"] for v in violations}
    assert "HL-BOTTOM-WASTE-01" not in rule_ids


def test_large_bottom_waste_above_report_floor_is_reported() -> None:
    thresholds = TemplateLayoutThresholds(
        hl_waste_sparse_ka_max_in=1.0,
        hl_dense_fill_min_effective_util=0.55,
        container_underutilization_max_util=0.55,
    )
    waste = CONTAINER_WASTE_REPORT_MIN_IN + 0.25
    slide = {
        "slide_index": 5,
        "title": "Delivery Status – Test",
        "highlights": {
            "effective_utilization_ratio": 0.2,
            "utilization_ratio": 0.2,
        },
        "hl_waste_below_text_in": waste,
    }
    violations = detect_container_space_violations(slide, thresholds=thresholds)
    rule_ids = {v["rule_id"] for v in violations}
    assert "HL-BOTTOM-WASTE-01" in rule_ids


def test_should_report_container_waste_uses_report_floor() -> None:
    assert not should_report_container_waste(1.44, 0.12)
    assert should_report_container_waste(2.25, 0.12)


def test_flags_hl_top_waste_only_above_report_floor() -> None:
    thresholds = TemplateLayoutThresholds(hl_waste_above_text_max_in=0.15)
    slide = {
        "slide_index": 3,
        "title": "Delivery Status – Test",
        "highlights": {"effective_utilization_ratio": 0.9},
        "hl_waste_above_text_in": 0.22,
        "hl_waste_below_text_in": 0.45,
    }
    violations = detect_container_space_violations(slide, thresholds=thresholds)
    rule_ids = {v["rule_id"] for v in violations}
    assert "HL-TOP-WASTE-01" not in rule_ids
    assert "HL-BOTTOM-WASTE-01" not in rule_ids


def test_flags_ka_waste_regions_only_above_report_floor() -> None:
    thresholds = TemplateLayoutThresholds(
        ka_waste_above_text_max_in=0.15,
        ka_waste_below_text_max_in=0.25,
        container_underutilization_max_util=0.55,
        container_combined_waste_min_in=0.35,
    )
    slide = {
        "slide_index": 5,
        "title": "Delivery Status – Test",
        "key_activities": {"item_count": 2, "utilization_ratio": 0.33},
        "ka_waste_above_text_in": 0.18,
        "ka_waste_below_text_in": 0.40,
    }
    violations = detect_container_space_violations(slide, thresholds=thresholds)
    rule_ids = {v["rule_id"] for v in violations}
    assert "KA-TOP-WASTE-01" not in rule_ids
    assert "KA-BOTTOM-WASTE-01" not in rule_ids
