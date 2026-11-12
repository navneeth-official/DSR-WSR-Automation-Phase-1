from datetime import date

import pytest

from monthly_report.data import resolve_report_period


def test_explicit_start_end_defaults_meeting_to_end():
    start, end, meeting = resolve_report_period(
        start_raw="2026-10-01",
        end_raw="2026-10-31",
        meeting_raw="",
    )
    assert (start, end, meeting) == (
        date(2026, 10, 1),
        date(2026, 10, 31),
        date(2026, 10, 31),
    )


def test_explicit_meeting_date_kept():
    start, end, meeting = resolve_report_period(
        start_raw="2026-10-01",
        end_raw="2026-10-31",
        meeting_raw="2026-10-20",
    )
    assert meeting == date(2026, 10, 20)
    assert start == date(2026, 10, 1)
    assert end == date(2026, 10, 31)


def test_legacy_meeting_date_uses_calendar_month():
    start, end, meeting = resolve_report_period(
        start_raw="",
        end_raw="",
        meeting_raw="2026-10-20",
    )
    assert (start, end, meeting) == (
        date(2026, 10, 1),
        date(2026, 10, 31),
        date(2026, 10, 20),
    )


def test_start_without_end_errors():
    with pytest.raises(ValueError):
        resolve_report_period(start_raw="2026-10-01", end_raw="", meeting_raw="")


def test_start_after_end_errors():
    with pytest.raises(ValueError):
        resolve_report_period(
            start_raw="2026-11-01",
            end_raw="2026-10-01",
            meeting_raw="",
        )
