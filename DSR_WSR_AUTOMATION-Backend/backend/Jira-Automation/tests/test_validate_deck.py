"""Tests for production deck validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.validation.content_checks import detect_content_violations
from app.validation.severity import deck_passes, normalize_severity
from app.validation.user_messages import enrich_finding

ROOT = Path(__file__).resolve().parents[1]
HASKELL_JULY = ROOT / "output" / "HEB_Delivery_Status_Haskell_July2025.pptx"
HASKELL_TEMPLATE = (
    ROOT / "templates" / "G10X H-E-B WSR Haskell Location Pharmacy GSS PAM 11 July 2025.pptx"
)
PPT_CONTENT = ROOT / "output" / "ppt_content.json"


def test_typography_violation_is_fail():
    violation = {"rule_id": "HL-P-05", "severity": "major", "message": "Story line must use 12pt"}
    assert normalize_severity(violation) == "fail"


def test_title_dash_is_warn():
    violation = {"rule_id": "TITLE-01", "severity": "major", "message": "Wrong dash"}
    assert normalize_severity(violation) == "warn"


def test_enrich_finding_has_fix_steps():
    finding = enrich_finding(
        {
            "rule_id": "HL-WASTE-01",
            "severity": "critical",
            "slide_index": 5,
            "title": "Delivery status – Cost Core Service",
            "hl_waste_below_text_in": 0.52,
            "limit_in": 0.12,
        },
        severity="fail",
    )
    assert finding["issue"].startswith("Too much empty space")
    assert finding["fix_steps"]
    assert finding["severity"] == "fail"
    assert "rule_id" in finding


def test_missing_project_content_violation():
    content = {
        "slides": [
            {
                "title": "Cost Core Service",
                "sections": [{"completed": ["Story A"], "released": [], "inprogress": []}],
                "key_activities": [],
            }
        ]
    }
    deck_data = {"slides": []}
    violations = detect_content_violations(deck_data, content)
    assert any(v["rule_id"] == "CONTENT-PRJ-01" for v in violations)


def test_missing_story_content_violation():
    content = {
        "slides": [
            {
                "title": "Cost Core Service",
                "sections": [
                    {
                        "completed": ["Implement buyer adjustment replay"],
                        "released": [],
                        "inprogress": [],
                    }
                ],
                "key_activities": [],
            }
        ]
    }
    deck_data = {
        "slides": [
            {
                "slide_index": 2,
                "title": "Delivery status – Cost Core Service",
                "is_contd": False,
                "highlights": {
                    "paragraphs": [
                        {"role": "story_item", "text": "Some other story"},
                    ]
                },
            }
        ]
    }
    violations = detect_content_violations(deck_data, content)
    assert any(v["rule_id"] == "CONTENT-HL-02" for v in violations)


def test_deck_passes_only_when_no_fail():
    assert deck_passes([{"severity": "warn"}, {"severity": "warn"}])
    assert not deck_passes([{"severity": "fail"}])


def test_sprint_line_secondary_run_manrope_light_passes():
    """Sprint lines use bold Manrope then Manrope Light for dates — same as template."""
    from app.services.ppt_hl_typography import detect_hl_typography_violations
    from app.services.template_typography import RoleStyleSpec, TemplateTypographySpec

    typography = TemplateTypographySpec(
        template_file="test.pptx",
        roles={
            "sprint_line": RoleStyleSpec(
                allowed_fonts=frozenset({"+mn-lt", "Manrope", "manrope light"}),
                size_pt=12.0,
                bold=True,
            )
        },
    )
    hl = {
        "paragraphs": [
            {
                "role": "sprint_line",
                "text": "Sprint – Q3.01 FY26 Phoenix, inprogress (Jun 01 – Jun 15)",
                "runs": [
                    {
                        "text": "Sprint – Q3.01 FY26 Phoenix, inprogress ",
                        "font": "Manrope",
                        "size_pt": 12.0,
                        "bold": True,
                    },
                    {
                        "text": "(Jun 01 – Jun 15) Stories (Total – 1)",
                        "font": "Manrope Light",
                        "size_pt": 12.0,
                        "bold": False,
                    },
                ],
            }
        ]
    }
    violations = detect_hl_typography_violations(hl, typography=typography)
    assert [v for v in violations if v["rule_id"] == "HL-P-02"] == []


def test_hl_ka_gap_at_builder_target_is_not_excessive():
    from app.services.ppt_format_violations import _excessive_hl_ka_spacing, load_thresholds

    thresholds = load_thresholds()
    slide = {
        "key_activities": {"item_count": 0},
        "hl_ka_gap_in": 0.472,
    }
    assert _excessive_hl_ka_spacing(slide, thresholds) is None


def test_ka_plc_04_only_flags_terminal_project_slide():
    from app.services.ppt_format_violations import detect_slide_violations, load_thresholds

    thresholds = load_thresholds()
    slide = {
        "slide_index": 10,
        "title": "Delivery status – Example Service",
        "is_contd": False,
        "highlights": {
            "position_in": {"bottom": 4.0},
            "paragraphs": [{"role": "story_item", "text": "Story"}],
        },
        "hl_bottom_measured_in": 4.0,
        "hl_text_bottom_for_fit_in": 3.0,
        "estimated_text_bottom_in": 3.0,
    }
    violations = detect_slide_violations(
        slide,
        thresholds=thresholds,
        ka_placement_terminal_indices=frozenset({11}),
    )
    assert not any(v["rule_id"] == "KA-PLC-04" for v in violations)

    violations = detect_slide_violations(
        slide,
        thresholds=thresholds,
        ka_placement_terminal_indices=frozenset({10}),
    )
    assert any(v["rule_id"] == "KA-PLC-04" for v in violations)


@pytest.mark.skipif(not HASKELL_JULY.is_file(), reason="Sample output deck missing")
def test_extract_finds_highlights_with_week_ending_header():
    """Regression: header 'Highlights of week ending …' must not break extraction."""
    from app.services.ppt_format_extractor import extract_deck
    from app.validation.content_checks import _index_deck_slides, _story_lines

    deck = extract_deck(HASKELL_JULY, use_rendered_bounds=False)
    entry = _index_deck_slides(deck)["cost core service"]
    stories = []
    for slide in [entry["main"], *entry["contd"]]:
        if slide:
            stories.extend(_story_lines(slide))
    assert len(stories) >= 6


@pytest.mark.skipif(not HASKELL_JULY.is_file(), reason="Sample output deck missing")
@pytest.mark.skipif(not PPT_CONTENT.is_file(), reason="ppt_content.json missing")
def test_cost_core_stories_match_json_when_both_present():
    from app.services.ppt_format_extractor import extract_deck
    from app.validation.content_checks import detect_content_violations, load_content_json

    deck = extract_deck(HASKELL_JULY, use_rendered_bounds=False)
    content = load_content_json(PPT_CONTENT)
    violations = detect_content_violations(deck, content)
    cost_hl = [
        v
        for v in violations
        if v.get("rule_id") == "CONTENT-HL-02" and v.get("project") == "Cost Core Service"
    ]
    assert cost_hl == []


@pytest.mark.skipif(not HASKELL_TEMPLATE.is_file(), reason="Haskell template missing")
def test_template_typography_extracts_calibri_13():
    from app.services.template_typography import extract_template_typography

    spec = extract_template_typography(HASKELL_TEMPLATE)
    assert "Calibri" in spec.header.allowed_fonts
    assert spec.header.size_pt == 16.0
    sprint = spec.roles.get("sprint_line")
    assert sprint is not None
    assert sprint.size_pt == 13.0
    assert "Calibri" in sprint.allowed_fonts


@pytest.mark.skipif(not HASKELL_JULY.is_file(), reason="Sample output deck missing")
@pytest.mark.skipif(not HASKELL_TEMPLATE.is_file(), reason="Haskell template missing")
def test_calibri_deck_passes_typography_against_haskell_template():
    from app.services.ppt_format_extractor import extract_deck
    from app.services.ppt_hl_typography import detect_hl_typography_violations
    from app.services.template_typography import extract_template_typography

    typography = extract_template_typography(HASKELL_TEMPLATE)
    deck = extract_deck(HASKELL_JULY, use_rendered_bounds=False)
    slide = next(s for s in deck["slides"] if s["slide_index"] == 4)
    violations = detect_hl_typography_violations(
        slide["highlights"],
        slide_index=4,
        typography=typography,
    )
    assert violations == []


@pytest.mark.skipif(not HASKELL_JULY.is_file(), reason="Sample output deck missing")
@pytest.mark.skipif(not HASKELL_TEMPLATE.is_file(), reason="Haskell template missing")
def test_validate_haskell_july_deck_runs():
    from app.validation.engine import validate_deck

    result = validate_deck(
        HASKELL_JULY,
        template_path=HASKELL_TEMPLATE,
        annotate=False,
        use_rendered_bounds=False,
    )
    assert result.report_json.is_file()
    assert result.report_md.is_file()
    assert isinstance(result.deck_pass, bool)
