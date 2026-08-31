"""Format sprint dates for PPT display (always from DB — never clipped to WSR range)."""

from __future__ import annotations

from datetime import date
from typing import Any


def format_sprint_dates_for_display(
    sprint_start: date | None,
    sprint_end: date | None,
) -> str:
    """
    G10X sprint line date range, e.g. ``Jun 04 – Jun 17``.

    Uses the sprint's full ``sprint_start_date`` and ``sprint_end_date`` from the
    ``sprints`` table. The WSR report window controls sprint *selection* only;
    it must never trim the dates shown on the slide.
    """
    if sprint_start and sprint_end:
        return f"{sprint_start.strftime('%b %d')} \u2013 {sprint_end.strftime('%b %d')}"
    if sprint_start:
        return sprint_start.strftime("%b %d")
    if sprint_end:
        return sprint_end.strftime("%b %d")
    return ""


def sprint_dates_from_section(section: dict[str, Any]) -> str:
    """
    Resolve the sprint date string for any slide section.

    Prefers ``sprint_start_date`` / ``sprint_end_date`` (ISO, from DB) over a
    pre-formatted ``sprint_dates`` string so every sprint is handled the same way.
    """
    start_raw = section.get("sprint_start_date")
    end_raw = section.get("sprint_end_date")
    if start_raw or end_raw:
        start = date.fromisoformat(start_raw) if start_raw else None
        end = date.fromisoformat(end_raw) if end_raw else None
        return format_sprint_dates_for_display(start, end)
    return section.get("sprint_dates", "")
