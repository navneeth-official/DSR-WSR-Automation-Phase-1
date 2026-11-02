"""Per-sprint counts shown on the monthly Delivery Updates slide."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from monthly_report.data import SprintStories

ENDED = "Ended"
IN_PROGRESS = "In-Progress"

COMPLETED = "completed"
IN_REVIEW = "in_review"
IN_PROGRESS_CATEGORY = "in_progress"
OTHER = "other"

_STATUS_CATEGORIES: dict[str, str] = {
    "done": COMPLETED,
    "closed": COMPLETED,
    "resolved": COMPLETED,
    "in review": IN_REVIEW,
    "in progress": IN_PROGRESS_CATEGORY,
    "in development": IN_PROGRESS_CATEGORY,
}

_ENDED_SPRINT_STATUSES = frozenset({"ended", "closed", "completed"})


def story_category(status: str | None) -> str:
    normalized = re.sub(r"[\s_-]+", " ", (status or "").strip().lower())
    return _STATUS_CATEGORIES.get(normalized, OTHER)


def sprint_display_status(db_status: str | None, end_date: date, meeting_date: date) -> str:
    """sprints.sprint_status, except a sprint that finished before the meeting is Ended."""
    compact = re.sub(r"[^a-z]", "", (db_status or "").lower())
    if compact in _ENDED_SPRINT_STATUSES or end_date < meeting_date:
        return ENDED
    return IN_PROGRESS


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


def compute_sprint_metrics(sprint: SprintStories, meeting_date: date) -> SprintMetrics:
    counts = {COMPLETED: 0, IN_REVIEW: 0, IN_PROGRESS_CATEGORY: 0, OTHER: 0}
    for status in sprint.story_statuses:
        counts[story_category(status)] += 1

    status = sprint_display_status(sprint.sprint_status, sprint.end_date, meeting_date)
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
