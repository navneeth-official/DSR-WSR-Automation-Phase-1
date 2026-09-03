"""Tests for missing-bold typography detection and validation summaries."""

from __future__ import annotations

from app.services.ppt_hl_typography import detect_hl_typography_violations
from app.services.template_typography import RoleStyleSpec, TemplateTypographySpec
from app.validation.metrics_summary import build_slide_check_summaries


def test_missing_bold_on_other_role_is_flagged() -> None:
    typography = TemplateTypographySpec(
        template_file="template.pptx",
        roles={
            "other": RoleStyleSpec(
                allowed_fonts=frozenset({"Calibri", "+mn-lt"}),
                size_pt=14.0,
                bold=True,
            ),
        },
    )
    hl = {
        "paragraphs": [
            {
                "role": "other",
                "text": "Fix grace period not applied",
                "runs": [{"text": "Fix grace period not applied", "font": "Calibri", "size_pt": 14.0}],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=typography)
    assert violations
    assert violations[0]["rule_id"] == "HL-P-05"
    assert violations[0]["details"][0]["issue"] == "not_bold"


def test_slide_summary_includes_typography_audit_rows() -> None:
    class Slide:
        slide_index = 5
        title = "Delivery Status – Test"
        deterministic_pass = False
        deterministic_score = 80.0
        violations = [
            {
                "source": "deterministic",
                "rule_id": "HL-P-05",
                "severity": "major",
                "slide_index": 5,
                "title": "Delivery Status – Test",
                "message": "Story must match template",
                "details": [{"role": "other", "issue": "not_bold"}],
            }
        ]

    typography = TemplateTypographySpec(
        template_file="template.pptx",
        roles={
            "story_item": RoleStyleSpec(
                allowed_fonts=frozenset({"Calibri"}),
                size_pt=14.0,
                bold=False,
            ),
        },
    )
    deck_data = {
        "slides": [
            {
                "slide_index": 5,
                "title": "Delivery Status – Test",
                "highlights": {
                    "paragraphs": [
                        {
                            "role": "story_item",
                            "text": "Sample story",
                            "runs": [{"text": "Sample story", "font": "Calibri", "size_pt": 14.0}],
                        },
                    ],
                },
            },
        ],
    }
    summaries = build_slide_check_summaries([Slide()], deck_data, typography=typography)
    assert summaries
    typo = summaries[0]["checks"]["typography"]
    assert typo["status"] == "fail"
    assert typo["paragraphs_audited"]
