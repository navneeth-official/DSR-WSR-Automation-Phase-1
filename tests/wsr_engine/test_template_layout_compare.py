"""Tests for template-vs-generated layout comparison."""

from __future__ import annotations

from app.services.template_layout_compare import detect_template_layout_deviations
from app.services.template_layout_spec import BoxGeometry, TemplateLayoutSpec


def _layout_spec() -> TemplateLayoutSpec:
    return TemplateLayoutSpec(
        template_file="template.pptx",
        prototype_slide_count=1,
        hl=BoxGeometry(top=1.0, left=0.5, width=9.0, height=2.5, bottom=3.5),
        ka=BoxGeometry(top=3.7, left=0.5, width=9.0, height=1.8, bottom=5.5),
        hl_ka_gap_in=0.2,
        title_top_in=0.3,
        position_tolerance_in=0.03,
        size_tolerance_in=0.04,
    )


def test_layout_compare_flags_hl_top_deviation() -> None:
    slide = {
        "slide_index": 3,
        "title": "Delivery status – Test",
        "highlights": {
            "position_in": {"top": 1.15, "left": 0.5, "width": 9.0, "height": 2.5},
            "effective_utilization_ratio": 0.9,
        },
    }
    violations = detect_template_layout_deviations(
        slide,
        layout_spec=_layout_spec(),
    )
    assert any(v["rule_id"] == "LAY-HL-TOP" for v in violations)


def test_layout_compare_ignores_contd_slides() -> None:
    slide = {
        "slide_index": 4,
        "title": "Delivery status – Test (Contd…)",
        "is_contd": True,
        "highlights": {
            "position_in": {"top": 2.0, "left": 0.5, "width": 9.0, "height": 2.5},
        },
    }
    violations = detect_template_layout_deviations(slide, layout_spec=_layout_spec())
    assert violations == []


def test_layout_compare_skips_when_within_tolerance() -> None:
    slide = {
        "slide_index": 3,
        "title": "Delivery status – Test",
        "highlights": {
            "position_in": {"top": 1.01, "left": 0.51, "width": 9.02, "height": 2.5},
            "effective_utilization_ratio": 0.9,
        },
    }
    violations = detect_template_layout_deviations(slide, layout_spec=_layout_spec())
    assert violations == []
