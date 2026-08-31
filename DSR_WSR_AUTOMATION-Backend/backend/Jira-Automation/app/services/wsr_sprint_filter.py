"""WSR sprint date-range filtering helpers."""

from __future__ import annotations

from datetime import date


def sprint_overlaps_wsr_range(
    sprint_start: date | None,
    sprint_end: date | None,
    wsr_start: date,
    wsr_end: date,
) -> bool:
    """
    Return True when the sprint duration intersects the WSR window (inclusive).

    Overlap condition (both sprint bounds required):
        sprint_start <= wsr_end AND sprint_end >= wsr_start

    When only one sprint bound is stored, fall back to that date falling inside
    the WSR range so partially populated sprint rows are not silently dropped.
    """
    if sprint_start is not None and sprint_end is not None:
        return sprint_start <= wsr_end and sprint_end >= wsr_start
    if sprint_start is not None:
        return wsr_start <= sprint_start <= wsr_end
    if sprint_end is not None:
        return wsr_start <= sprint_end <= wsr_end
    return False
