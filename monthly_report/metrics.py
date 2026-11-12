"""Per-sprint counts shown on the monthly Delivery Updates slide."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from monthly_report.data import SprintStories

ENDED = "Ended"
IN_PROGRESS = "In-Progress"

COMPLETED = "completed"
IN_REVIEW = "in_review"
IN_PROGRESS_CATEGORY = "in_progress"
OTHER = "other"

STATUS_CATEGORIES_FILE = Path(__file__).resolve().parents[1] / "config" / "monthly_status_categories.json"

_DEFAULT_STATUS_CATEGORIES: dict[str, str] = {
    "done": COMPLETED,
    "closed": COMPLETED,
    "resolved": COMPLETED,
    "in review": IN_REVIEW,
    "in progress": IN_PROGRESS_CATEGORY,
    "in development": IN_PROGRESS_CATEGORY,
}
_CATEGORIES = frozenset({COMPLETED, IN_REVIEW, IN_PROGRESS_CATEGORY, OTHER})


def _normalize_status(status: str | None) -> str:
    return re.sub(r"[\s_-]+", " ", (status or "").strip().lower())


@lru_cache(maxsize=1)
def status_categories() -> dict[str, str]:
    """Jira status name -> bucket. ``config/monthly_status_categories.json`` overrides defaults."""
    if not STATUS_CATEGORIES_FILE.is_file():
        return dict(_DEFAULT_STATUS_CATEGORIES)
    raw: dict[str, list[str]] = json.loads(STATUS_CATEGORIES_FILE.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for category, statuses in raw.items():
        if category not in _CATEGORIES:
            raise ValueError(
                f"{STATUS_CATEGORIES_FILE.name}: unknown category {category!r}; "
                f"use one of {sorted(_CATEGORIES)}"
            )
        for status in statuses:
            mapping[_normalize_status(status)] = category
    return mapping


def story_category(status: str | None) -> str:
    return status_categories().get(_normalize_status(status), OTHER)


def sprint_display_status(
    start_date: date,
    end_date: date,
    period_start: date,
    period_end: date,
) -> str:
    """
    Derive Ended vs In-Progress from sprint dates vs the MSR window.

    Ignores ``sprints.sprint_status``. For a sprint that overlaps
    ``[period_start, period_end]``, it is In-Progress only when the sprint
    continues past the MSR end date (``start_date <= period_end < end_date``).
    If ``end_date == period_end`` (or earlier), the sprint is Ended.
    """
    overlaps = start_date <= period_end and end_date >= period_start
    if overlaps and start_date <= period_end < end_date:
        return IN_PROGRESS
    return ENDED


@dataclass(frozen=True)
class SprintMetrics:
    sprint_name: str
    start_date: date
    end_date: date
    status: str
    db_status: str | None
    total: int
    completed: int
    in_review: int
    in_progress: int
    other: int
    spill_over: int | None

    @property
    def is_ended(self) -> bool:
        return self.status == ENDED


def compute_sprint_metrics(
    sprint: SprintStories,
    period_start: date,
    period_end: date,
) -> SprintMetrics:
    counts = {COMPLETED: 0, IN_REVIEW: 0, IN_PROGRESS_CATEGORY: 0, OTHER: 0}
    for status in sprint.story_statuses:
        counts[story_category(status)] += 1

    status = sprint_display_status(
        sprint.start_date,
        sprint.end_date,
        period_start,
        period_end,
    )
    spill_over = counts[IN_REVIEW] + counts[IN_PROGRESS_CATEGORY] if status == ENDED else None
    # TC = chart categories only; To Do / other statuses are omitted from the total.
    total = counts[COMPLETED] + counts[IN_REVIEW] + counts[IN_PROGRESS_CATEGORY]

    return SprintMetrics(
        sprint_name=sprint.sprint_name,
        start_date=sprint.start_date,
        end_date=sprint.end_date,
        status=status,
        db_status=sprint.sprint_status,
        total=total,
        completed=counts[COMPLETED],
        in_review=counts[IN_REVIEW],
        in_progress=counts[IN_PROGRESS_CATEGORY],
        other=counts[OTHER],
        spill_over=spill_over,
    )
