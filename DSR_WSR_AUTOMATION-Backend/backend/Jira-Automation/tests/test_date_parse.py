from datetime import date

import pytest

from app.utils.date_parse import parse_flexible_date


def test_parse_iso_date() -> None:
    assert parse_flexible_date("2026-07-27") == date(2026, 7, 27)


def test_parse_jira_timestamp_with_timezone() -> None:
    assert parse_flexible_date("2026-06-01T13:34:39.968-0500") == date(2026, 6, 1)


def test_parse_jira_timestamp_zulu() -> None:
    assert parse_flexible_date("2026-07-24T01:43:48.555Z") == date(2026, 7, 24)


def test_parse_none_and_empty() -> None:
    assert parse_flexible_date(None) is None
    assert parse_flexible_date("") is None
    assert parse_flexible_date("   ") is None


def test_parse_date_instance() -> None:
    assert parse_flexible_date(date(2026, 1, 2)) == date(2026, 1, 2)


def test_parse_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_flexible_date("not-a-date")
