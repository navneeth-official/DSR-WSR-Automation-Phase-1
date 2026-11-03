"""Format sprint dates and status for PPT display.

Sprint dates always come from the database and are never clipped to the WSR range.
The status word on the sprint line is In-progress only when the sprint continues
past the report week; otherwise it is Ended.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

_ENDED_STATUSES = {"ended", "end", "closed", "complete", "completed", "done"}
_IN_PROGRESS_STATUSES = {
    "in progress",
    "inprogress",
    "active",
    "open",
    "wip",
    "started",
}


def _normalize_sprint_status(raw: str | None) -> str:
    return re.sub(r"[\s_\-]+", " ", (raw or "").strip().lower())


def format_sprint_status_label(
    db_status: str | None = None,
    *,
    sprint_end: date | None = None,
    report_end: date | None = None,
) -> str:
    """Slide label before the sprint dates: ``In-progress`` or ``Ended``.

    A sprint is In-progress only when its end date is after the WSR week, so it
    continues into an upcoming week. A sprint that finishes during or before the
    report week is Ended. Stored values such as ``inprogress`` are not shown.
    """
    if sprint_end is not None and report_end is not None:
        if sprint_end > report_end:
            return "In-progress"
        return "Ended"

    key = _normalize_sprint_status(db_status).replace(" ", "")
    if key in _ENDED_STATUSES or _normalize_sprint_status(db_status) in _ENDED_STATUSES:
        return "Ended"
    if key in {item.replace(" ", "") for item in _IN_PROGRESS_STATUSES}:
        return "In-progress"
    if db_status and db_status.strip():
        text = db_status.strip()
        if text.lower() == "in-progress":
            return "In-progress"
        if text.lower() == "ended":
            return "Ended"
    return "In-progress"


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
