"""Fill the monthly cadence cover slide (track name and meeting date)."""

from __future__ import annotations

from datetime import date

from monthly_report.delivery_slide import _MONTH_ABBREVIATIONS
from monthly_report.tokens import find_tokens, replace_tokens_in_text_frame


def format_cover_meeting_date(value: date) -> str:
    """Display date for ``{{Date}}`` on the cover (e.g. ``20 Jun 2026``)."""
    month = _MONTH_ABBREVIATIONS[value.month - 1]
    return f"{value.day:02d} {month} {value.year}"


def fill_cover_slide(
    slide,
    *,
    track_name: str,
    meeting_date: date,
) -> list[str]:
    """
    Replace ``{{Track Name}}``, ``{{TRACK NAME}}``, and ``{{Date}}`` on the first slide.

    Returns unresolved placeholder strings (e.g. when ``track_name`` is empty).
    """
    values = {
        "track_name": track_name.strip(),
        "date": format_cover_meeting_date(meeting_date),
    }
    leftovers: list[str] = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            leftovers.extend(replace_tokens_in_text_frame(shape.text_frame, values))
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    if cell.text_frame:
                        leftovers.extend(replace_tokens_in_text_frame(cell.text_frame, values))
    return leftovers


def cover_leftover_tokens(slide) -> list[str]:
    found: list[str] = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            found.extend(find_tokens(shape.text_frame.text))
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    found.extend(find_tokens(cell.text_frame.text))
    return found
