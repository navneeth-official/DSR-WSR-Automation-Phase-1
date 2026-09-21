"""Tests for typography false-positive fixes and sprint mixed-bold checks."""

from __future__ import annotations

from app.services.ppt_hl_typography import detect_hl_typography_violations
from app.services.template_typography import RoleStyleSpec, TemplateTypographySpec
from app.validation.typography_display import enrich_paragraph_row


def _typography() -> TemplateTypographySpec:
    body = RoleStyleSpec(
        allowed_fonts=frozenset({"Calibri", "+mn-lt"}),
        size_pt=13.0,
        bold=False,
    )
    return TemplateTypographySpec(
        template_file="template.pptx",
        roles={
            "sprint_line": RoleStyleSpec(
                allowed_fonts=frozenset({"Calibri", "+mn-lt"}),
                size_pt=13.0,
                bold=True,
            ),
            "story_item": body,
        },
    )


def test_flags_alien_font_even_on_short_glue_word() -> None:
    hl = {
        "paragraphs": [
            {
                "role": "story_item",
                "text": "Implement warehouse list page UI with search, sort, and pagination",
                "runs": [
                    {"text": "Implement warehouse list page UI ", "font": "Calibri", "size_pt": 13.0},
                    {"text": "with", "font": "Bookman Old Style", "size_pt": 13.0},
                    {"text": " search, sort, and pagination", "font": "Calibri", "size_pt": 13.0},
                ],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=_typography())
    assert violations
    assert violations[0]["rule_id"] == "HL-P-05"
    assert violations[0]["details"][0]["issue"] == "wrong_font"
    assert violations[0]["details"][0]["text"] == "with"


def test_ignores_theme_alias_on_short_glue_word() -> None:
    hl = {
        "paragraphs": [
            {
                "role": "story_item",
                "text": "Fix bulk price update job timeout for large stores with 50k+ SKUs",
                "runs": [
                    {"text": "Fix bulk price update job timeout for large stores ", "font": "Calibri", "size_pt": 13.0},
                    {"text": "with", "font": "+mn-lt", "size_pt": 13.0},
                    {"text": " 50k+ SKUs", "font": "Calibri", "size_pt": 13.0},
                ],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=_typography())
    assert violations == []


def test_flags_extra_blanks_after_current_week_from_template() -> None:
    from app.services.template_spacing_spec import (
        TemplateSpacingSpec,
        detect_hl_spacing_violations,
    )

    spacing = TemplateSpacingSpec(max_blanks_after_current_week=0)
    hl = {
        "paragraphs": [
            {"role": "sprint_line", "text": "Sprint – Test"},
            {"role": "current_week", "text": "Current week sprint status"},
            {"role": "blank", "text": ""},
            {"role": "blank", "text": ""},
            {"role": "category_completed", "text": "Stories completed this week – 1 stories"},
        ],
    }
    violations = detect_hl_spacing_violations(hl, spacing=spacing)
    assert violations
    assert violations[0]["rule_id"] == "HL-SPC-03"
    assert violations[0]["details"][0]["issue"] == "extra_blanks_after_current_week"


def test_flags_sprint_stats_portion_bold_as_violation() -> None:
    hl = {
        "paragraphs": [
            {
                "role": "sprint_line",
                "text": (
                    "Sprint – Q2.14 FY26 Fornax, Ended (30 Apr 2026 – 14 May 2026) "
                    "Stories (Total – 1, Completed – 1, In-Progress – 1, In-Review – 1)"
                ),
                "runs": [
                    {"text": "Sprint – Q2.14 FY26 Fornax, Ended ", "font": "Calibri", "size_pt": 13.0, "bold": True},
                    {"text": "(30 Apr 2026 – 14 May 2026) ", "font": "Calibri", "size_pt": 13.0, "bold": None},
                    {"text": "Stories", "font": "Calibri", "size_pt": 13.0, "bold": True},
                    {"text": " (Total – 1)", "font": "Calibri", "size_pt": 13.0, "bold": None},
                ],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=_typography())
    assert violations
    assert violations[0]["rule_id"] == "HL-P-02"
    assert violations[0]["details"][0]["issue"] == "unexpected_bold"
    assert violations[0]["details"][0]["text"] == "Stories"


def test_enrich_paragraph_matches_by_paragraph_index_not_substring() -> None:
    row = {
        "paragraph_index": 4,
        "role": "story_item",
        "text_preview": "Implement warehouse creation UI with validation and navigation features",
        "font": "Calibri",
        "size_pt": 13.0,
        "bold": False,
        "expected_fonts": ["Calibri"],
        "expected_size_pt": 13.0,
        "expected_bold": False,
    }
    violations = [
        {
            "details": [
                {
                    "paragraph_index": 3,
                    "role": "story_item",
                    "issue": "wrong_font",
                    "font": "Bookman Old Style",
                    "text": "with",
                    "expected_fonts": ["Calibri"],
                }
            ]
        }
    ]
    enriched = enrich_paragraph_row(row, violations)
    assert enriched["status"] == "ok"


def test_current_week_accepts_template_decorative_status_font() -> None:
    typography = TemplateTypographySpec(
        template_file="template.pptx",
        roles={
            "current_week": RoleStyleSpec(
                allowed_fonts=frozenset({"Calibri", "Boucherie Block", "+mn-lt"}),
                size_pt=13.0,
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
                    {"text": "Current ", "font": "Calibri", "size_pt": 13.0},
                    {"text": "week sprint ", "font": "Calibri", "size_pt": 13.0},
                    {"text": "status", "font": "Boucherie Block", "size_pt": 13.0},
                ],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=typography)
    assert not violations


def test_sprint_line_accepts_template_completed_word_size() -> None:
    typography = TemplateTypographySpec(
        template_file="template.pptx",
        roles={
            "sprint_line": RoleStyleSpec(
                allowed_fonts=frozenset({"Calibri", "+mn-lt"}),
                size_pt=13.0,
                allowed_sizes_pt=frozenset({13.0, 16.0}),
                bold=True,
            ),
        },
    )
    hl = {
        "paragraphs": [
            {
                "role": "sprint_line",
                "text": "Sprint – Q3.01 FY26 Atlas, Ended (04 Jun 2026 – 17 Jun 2026) Stories (Total – 1, Completed – 1)",
                "runs": [
                    {"text": "Sprint – Q3.01 FY26 Atlas, Ended ", "font": "Calibri", "size_pt": 13.0, "bold": True},
                    {"text": "(04 Jun 2026 – 17 Jun 2026) ", "font": "Calibri", "size_pt": 13.0},
                    {"text": "Stories (Total – 1, ", "font": "Calibri", "size_pt": 13.0},
                    {"text": "Completed", "font": "Calibri", "size_pt": 16.0},
                    {"text": " – 1)", "font": "Calibri", "size_pt": 13.0},
                ],
            },
        ],
    }
    violations = detect_hl_typography_violations(hl, typography=typography)
    assert not violations
