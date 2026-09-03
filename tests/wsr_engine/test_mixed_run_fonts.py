"""Tests for per-run font validation within a paragraph."""

from __future__ import annotations

from app.services.ppt_hl_typography import detect_hl_typography_violations
from app.services.template_typography import RoleStyleSpec, TemplateTypographySpec


def test_flags_wrong_font_on_any_run_in_paragraph() -> None:
    typography = TemplateTypographySpec(
        template_file="template.pptx",
        roles={
            "current_week": RoleStyleSpec(
                allowed_fonts=frozenset({"Calibri", "+mn-lt"}),
                size_pt=14.0,
                bold=None,
            ),
        },
    )
    hl = {
        "paragraphs": [
            {
                "role": "current_week",
                "text": "Current week sprint status",
                "runs": [
                    {"text": "Current ", "font": "Calibri", "size_pt": 14.0},
                    {"text": "week ", "font": "Calibri", "size_pt": 14.0},
                    {"text": "sprint", "font": "Bookman Old Style", "size_pt": 14.0},
                    {"text": " status", "font": "Calibri", "size_pt": 14.0},
                ],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=typography)
    assert violations
    assert violations[0]["rule_id"] == "HL-P-03"
    assert violations[0]["details"][0]["issue"] == "wrong_font"
    assert violations[0]["details"][0]["font"] == "Bookman Old Style"


def test_flags_wrong_color_when_template_specifies_color() -> None:
    typography = TemplateTypographySpec(
        template_file="template.pptx",
        roles={
            "story_item": RoleStyleSpec(
                allowed_fonts=frozenset({"Calibri"}),
                size_pt=14.0,
                allowed_colors=frozenset({"000000"}),
            ),
        },
    )
    hl = {
        "paragraphs": [
            {
                "role": "story_item",
                "text": "Fix photo upload",
                "runs": [
                    {"text": "Fix photo upload", "font": "Calibri", "size_pt": 14.0, "color": "FF0000"},
                ],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=typography)
    assert violations
    assert violations[0]["details"][0]["issue"] == "wrong_color"
