"""Tests for sprint date display on PPT slides."""

from datetime import date

from app.services.sprint_display import format_sprint_dates_for_display


def test_full_sprint_range_unchanged_by_wsr():
    """DB dates must appear as-is — not clipped to a WSR window."""
    start = date(2026, 6, 4)
    end = date(2026, 6, 17)
    assert format_sprint_dates_for_display(start, end) == "Jun 04 – Jun 17"


def test_sprint_extends_past_wsr_end_still_shows_full_end():
    """Sprint ending after WSR end date still shows full sprint end."""
    start = date(2026, 6, 1)
    end = date(2026, 6, 20)
    assert format_sprint_dates_for_display(start, end) == "Jun 01 – Jun 20"


def test_start_only():
    assert format_sprint_dates_for_display(date(2026, 4, 16), None) == "Apr 16"


def test_empty():
    assert format_sprint_dates_for_display(None, None) == ""
