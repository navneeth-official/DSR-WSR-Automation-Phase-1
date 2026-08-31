"""Tests for WSR sprint overlap filtering."""

from datetime import date

from app.services.wsr_sprint_filter import sprint_overlaps_wsr_range

WSR_START = date(2026, 7, 7)
WSR_END = date(2026, 7, 13)


def test_sprint_starts_during_wsr_week():
    assert sprint_overlaps_wsr_range(
        date(2026, 7, 10), date(2026, 7, 20), WSR_START, WSR_END
    )


def test_sprint_ends_during_wsr_week():
    assert sprint_overlaps_wsr_range(
        date(2026, 6, 30), date(2026, 7, 9), WSR_START, WSR_END
    )


def test_sprint_fully_inside_wsr_week():
    assert sprint_overlaps_wsr_range(
        date(2026, 7, 8), date(2026, 7, 12), WSR_START, WSR_END
    )


def test_sprint_spans_across_entire_wsr_week():
    """Long-running sprint active throughout the WSR week."""
    assert sprint_overlaps_wsr_range(
        date(2026, 6, 30), date(2026, 7, 20), WSR_START, WSR_END
    )


def test_sprint_ends_before_wsr_week():
    assert not sprint_overlaps_wsr_range(
        date(2026, 6, 1), date(2026, 7, 6), WSR_START, WSR_END
    )


def test_sprint_starts_after_wsr_week():
    assert not sprint_overlaps_wsr_range(
        date(2026, 7, 14), date(2026, 7, 27), WSR_START, WSR_END
    )


def test_sprint_touching_wsr_start_boundary():
    assert sprint_overlaps_wsr_range(
        date(2026, 6, 1), date(2026, 7, 7), WSR_START, WSR_END
    )


def test_sprint_touching_wsr_end_boundary():
    assert sprint_overlaps_wsr_range(
        date(2026, 7, 13), date(2026, 7, 20), WSR_START, WSR_END
    )


def test_partial_dates_fallback_to_known_bound_in_range():
    assert sprint_overlaps_wsr_range(date(2026, 7, 8), None, WSR_START, WSR_END)
    assert sprint_overlaps_wsr_range(None, date(2026, 7, 8), WSR_START, WSR_END)


def test_partial_dates_fallback_excludes_out_of_range():
    assert not sprint_overlaps_wsr_range(date(2026, 8, 1), None, WSR_START, WSR_END)
    assert not sprint_overlaps_wsr_range(None, date(2026, 6, 1), WSR_START, WSR_END)


def test_no_sprint_dates():
    assert not sprint_overlaps_wsr_range(None, None, WSR_START, WSR_END)
