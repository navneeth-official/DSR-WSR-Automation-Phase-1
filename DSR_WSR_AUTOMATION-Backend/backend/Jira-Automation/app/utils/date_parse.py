"""Parse Jira / Rovo date strings into calendar dates (yyyy-mm-dd)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_ISO_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}")


def parse_flexible_date(value: Any) -> date | None:
    """
    Normalize assorted date inputs to a date.

    Accepts ``date``, ISO dates (``2026-07-27``), and Jira timestamps
    (``2026-06-01T13:34:39.968-0500``). Returns ``None`` for empty values.
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    s = str(value).strip()
    if not s:
        return None

    prefix_match = _ISO_DATE_PREFIX.match(s)
    if prefix_match:
        try:
            return date.fromisoformat(prefix_match.group(0))
        except ValueError:
            pass

    normalized = s.replace("Z", "+00:00")
    if (
        len(normalized) > 5
        and normalized[-5] in ("+", "-")
        and normalized[-3] != ":"
    ):
        normalized = f"{normalized[:-2]}:{normalized[-2:]}"

    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        pass

    raise ValueError(f"Unrecognized date value: {value!r}")
