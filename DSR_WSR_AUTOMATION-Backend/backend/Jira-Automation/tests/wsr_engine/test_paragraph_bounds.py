"""Tests for Highlights paragraph bound estimation."""

from __future__ import annotations

from app.validation.paragraph_bounds import estimate_hl_paragraph_rect_in, estimate_hl_run_rect_in


def test_estimate_paragraph_rect_by_index() -> None:
    slide_data = {
        "hl_content_top_in": 2.0,
        "hl_waste_above_text_in": 0.3,
        "highlights": {
            "position_in": {"left": 0.5, "width": 8.0},
            "paragraphs": [
                {"text": "", "role": "blank", "line_spacing_pt": 15.3},
                {"text": "", "role": "blank", "line_spacing_pt": 15.3},
                {"text": "Sprint line", "role": "sprint_line", "line_spacing_pt": 16.0},
                {"text": "Current week sprint status", "role": "current_week", "line_spacing_pt": 15.3},
                {"text": "- Story one", "role": "story_item", "line_spacing_pt": 15.3},
            ],
        },
    }
    rect = estimate_hl_paragraph_rect_in(
        slide_data,
        paragraph_index=3,
        paragraph_text="Current week sprint status",
    )
    assert rect is not None
    assert rect["top_in"] > 2.0 + 0.3
    assert rect["width_in"] > 0


def test_run_level_bounds_narrower_than_line() -> None:
    slide_data = {
        "hl_content_top_in": 2.0,
        "hl_waste_above_text_in": 0.0,
        "highlights": {
            "position_in": {"left": 0.5, "width": 8.0},
            "paragraphs": [
                {
                    "text": "Fix grace period on mobile timeclock",
                    "role": "story_item",
                    "level": 1,
                    "line_spacing_pt": 15.3,
                    "runs": [
                        {"text": "Fix grace period on ", "size_pt": 14.0},
                        {"text": "mobile", "size_pt": 24.0},
                        {"text": " timeclock", "size_pt": 14.0},
                    ],
                },
            ],
        },
    }
    detail = {
        "role": "story_item",
        "issue": "wrong_size",
        "text": "mobile",
        "paragraph_text": "Fix grace period on mobile timeclock",
        "paragraph_index": 0,
        "size_pt": 24.0,
    }
    line = estimate_hl_paragraph_rect_in(
        slide_data,
        paragraph_text=detail["paragraph_text"],
        paragraph_index=0,
    )
    run = estimate_hl_run_rect_in(slide_data, detail)
    assert line is not None and run is not None
    assert run["width_in"] < line["width_in"]
    assert run["left_in"] > line["left_in"]

    slide_data = {
        "hl_content_top_in": 2.0,
        "hl_waste_above_text_in": 0.0,
        "highlights": {
            "position_in": {"left": 0.5, "width": 8.0},
            "paragraphs": [
                {"text": "Sprint line", "role": "sprint_line", "line_spacing_pt": 16.0},
                {"text": "Current week sprint status", "role": "current_week", "line_spacing_pt": 15.3},
            ],
        },
    }
    rect = estimate_hl_paragraph_rect_in(
        slide_data,
        text="sprint",
        role="current_week",
        paragraph_text="Current week sprint status",
    )
    assert rect is not None
    sprint_rect = estimate_hl_paragraph_rect_in(
        slide_data,
        paragraph_text="Sprint line",
        role="sprint_line",
    )
    assert sprint_rect is not None
    assert rect["top_in"] > sprint_rect["top_in"]
