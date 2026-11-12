"""Deck-wide placeholders: track name, meeting date and report period.

They are filled on every slide that carries them (cover, footers, closing slide),
so the cover does not have to be the first slide.
"""

from __future__ import annotations

from datetime import date

from monthly_report.tokens import (
    DateValue,
    TokenValue,
    format_date,
    replace_tokens_in_shapes,
    tokens_in_shapes,
)

COVER_DATE_FORMAT = "DD MMM YYYY"
DECK_KEYS = frozenset(
    {"track_name", "date", "meeting_date", "period_start", "period_end", "report_period"}
)


def format_cover_meeting_date(value: date) -> str:
    """Default display for ``{{Date}}`` (e.g. ``20 Jun 2026``)."""
    return format_date(value, COVER_DATE_FORMAT)


def deck_values(
    *,
    track_name: str,
    meeting_date: date,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict[str, TokenValue]:
    meeting = DateValue(meeting_date, COVER_DATE_FORMAT)
    values: dict[str, TokenValue] = {
        "track_name": track_name.strip(),
        "date": meeting,
        "meeting_date": meeting,
    }
    if period_start is not None and period_end is not None:
        values["period_start"] = DateValue(period_start, COVER_DATE_FORMAT)
        values["period_end"] = DateValue(period_end, COVER_DATE_FORMAT)
        values["report_period"] = (
            f"{format_cover_meeting_date(period_start)} - {format_cover_meeting_date(period_end)}"
        )
    return values


def fill_deck_values(prs, values: dict[str, TokenValue]) -> None:
    for slide in prs.slides:
        replace_tokens_in_shapes(slide.shapes, values)


def fill_cover_slide(
    slide,
    *,
    track_name: str,
    meeting_date: date,
) -> list[str]:
    """Replace deck-wide placeholders on one slide; return the ones left unresolved."""
    values = deck_values(track_name=track_name, meeting_date=meeting_date)
    return replace_tokens_in_shapes(slide.shapes, values)


def cover_leftover_tokens(slide) -> list[str]:
    return tokens_in_shapes(slide.shapes)
