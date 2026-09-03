"""Tests for typography slide annotation."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from app.validation.annotate import annotate_finding_image


def test_annotates_typography_detail(tmp_path: Path) -> None:
    source = tmp_path / "slide.png"
    Image.new("RGB", (960, 540), color=(240, 240, 240)).save(source)

    slide_data = {
        "hl_content_top_in": 2.0,
        "highlights": {
            "position_in": {"left": 0.5, "width": 8.0, "top": 1.5, "bottom": 5.0},
            "paragraphs": [
                {
                    "text": "Current week sprint status",
                    "role": "current_week",
                    "line_spacing_pt": 15.3,
                },
            ],
        },
    }
    finding = {"rule_id": "HL-P-03", "annotation_label": "Wrong font size"}
    detail = {
        "role": "current_week",
        "issue": "wrong_font",
        "paragraph_index": 0,
        "text": "sprint",
        "paragraph_text": "Current week sprint status",
    }
    output = tmp_path / "annotated.png"
    annotate_finding_image(
        source,
        output,
        finding,
        slide_data,
        detail=detail,
        slide_index=3,
    )
    assert output.is_file()
    annotated = Image.open(output)
    assert annotated.size == (960, 540)


def test_annotates_spacing_blank_lines(tmp_path: Path) -> None:
    source = tmp_path / "slide.png"
    Image.new("RGB", (960, 540), color=(240, 240, 240)).save(source)

    slide_data = {
        "hl_content_top_in": 2.0,
        "hl_text_top_in": 2.0,
        "highlights": {
            "position_in": {"left": 0.5, "width": 8.0, "top": 1.5, "bottom": 5.0},
            "paragraphs": [
                {"text": "Sprint line", "role": "sprint_line", "line_spacing_pt": 15.3},
                {"text": "Current week sprint status", "role": "current_week", "line_spacing_pt": 15.3},
                {"text": "", "role": "blank", "line_spacing_pt": 15.3},
                {"text": "", "role": "blank", "line_spacing_pt": 15.3},
                {"text": "Stories completed", "role": "category_completed", "line_spacing_pt": 15.3},
            ],
        },
    }
    finding = {"rule_id": "HL-SPC-03", "annotation_label": "Extra blank line"}
    detail = {
        "issue": "extra_blanks_after_current_week",
        "paragraph_index": 1,
        "blank_count": 2,
    }
    output = tmp_path / "annotated_spacing.png"
    annotate_finding_image(
        source,
        output,
        finding,
        slide_data,
        detail=detail,
        slide_index=7,
    )
    assert output.is_file()
    from app.validation.paragraph_bounds import merge_hl_bounds_in, resolve_hl_spacing_blank_regions

    regions = resolve_hl_spacing_blank_regions(slide_data, detail)
    assert len(regions) == 2
    assert regions[0]["top_in"] < regions[1]["top_in"]
    merged = merge_hl_bounds_in(regions)
    assert merged is not None
    assert merged["height_in"] > regions[0]["height_in"]
