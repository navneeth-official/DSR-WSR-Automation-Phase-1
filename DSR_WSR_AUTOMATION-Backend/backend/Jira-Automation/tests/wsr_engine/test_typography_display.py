"""Tests for human-readable typography report labels."""

from __future__ import annotations

from app.validation.typography_display import (
    display_font_name,
    display_style,
    enrich_paragraph_row,
    expected_style,
    human_role_label,
)


def test_display_font_maps_theme_alias() -> None:
    assert display_font_name("+mn-lt") == "Calibri"


def test_enrich_paragraph_flags_missing_bold() -> None:
    row = {
        "role": "story_item",
        "text_preview": "Fix grace period",
        "font": "Calibri",
        "size_pt": 14.0,
        "bold": None,
        "expected_fonts": ["Calibri", "+mn-lt"],
        "expected_size_pt": 14.0,
        "expected_bold": False,
    }
    violations = [
        {
            "details": [
                {
                    "role": "story_item",
                    "issue": "wrong_size",
                    "text": "Fix grace period",
                    "expected_size_pt": 12.0,
                }
            ]
        }
    ]
    enriched = enrich_paragraph_row(row, violations)
    assert enriched["status"] == "fix"
    assert "Wrong size" in enriched["fix_hint"]
