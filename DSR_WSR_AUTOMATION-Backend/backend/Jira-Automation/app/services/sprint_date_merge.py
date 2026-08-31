"""Merge sprint date bounds from imports — widen only, never shrink."""

from __future__ import annotations

from datetime import date


def merge_sprint_start_date(
    existing: date | None,
    incoming: date | None,
) -> date | None:
    """Earliest known sprint start (canonical window grows earlier)."""
    if existing is None:
        return incoming
    if incoming is None:
        return existing
    return min(existing, incoming)


def merge_sprint_end_date(
    existing: date | None,
    incoming: date | None,
) -> date | None:
    """Latest known sprint end (canonical window grows later)."""
    if existing is None:
        return incoming
    if incoming is None:
        return existing
    return max(existing, incoming)
