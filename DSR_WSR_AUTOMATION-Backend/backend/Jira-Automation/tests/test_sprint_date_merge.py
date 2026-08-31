"""Tests for widening sprint date merge on import."""

from datetime import date

from app.services.sprint_date_merge import merge_sprint_end_date, merge_sprint_start_date


def test_merge_end_keeps_later_canonical_date():
  assert merge_sprint_end_date(date(2026, 6, 17), date(2026, 6, 12)) == date(2026, 6, 17)
  assert merge_sprint_end_date(date(2026, 6, 12), date(2026, 6, 17)) == date(2026, 6, 17)


def test_merge_start_keeps_earlier_canonical_date():
  assert merge_sprint_start_date(date(2026, 6, 4), date(2026, 6, 8)) == date(2026, 6, 4)
  assert merge_sprint_start_date(date(2026, 6, 8), date(2026, 6, 4)) == date(2026, 6, 4)


def test_merge_fills_missing_bounds():
  assert merge_sprint_end_date(None, date(2026, 6, 17)) == date(2026, 6, 17)
  assert merge_sprint_end_date(date(2026, 6, 17), None) == date(2026, 6, 17)
