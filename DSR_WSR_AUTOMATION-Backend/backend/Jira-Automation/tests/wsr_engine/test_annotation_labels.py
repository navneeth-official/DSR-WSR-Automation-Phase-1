"""Tests for validation annotation label merging and placement helpers."""

from __future__ import annotations

from app.validation.annotate import _merge_typography_details, _typography_label


def test_merge_typography_details_combines_issues_on_same_run() -> None:
    details = [
        {
            "paragraph_index": 3,
            "role": "current_week",
            "paragraph_text": "Current week sprint status",
            "text": "sprint",
            "issue": "wrong_font",
        },
        {
            "paragraph_index": 3,
            "role": "current_week",
            "paragraph_text": "Current week sprint status",
            "text": "sprint",
            "issue": "wrong_size",
        },
    ]
    merged = _merge_typography_details(details)
    assert len(merged) == 1
    assert set(merged[0]["issues"]) == {"wrong_font", "wrong_size"}
    assert _typography_label(merged[0]) == "Wrong font · Wrong size"


def test_merge_typography_details_keeps_separate_targets() -> None:
    details = [
        {
            "paragraph_index": 3,
            "role": "current_week",
            "paragraph_text": "Current week sprint status",
            "text": "sprint",
            "issue": "wrong_font",
        },
        {
            "paragraph_index": 5,
            "role": "story_item",
            "paragraph_text": "Fix photo evidence upload",
            "text": "Fix photo evidence upload",
            "issue": "wrong_font",
        },
    ]
    merged = _merge_typography_details(details)
    assert len(merged) == 2
