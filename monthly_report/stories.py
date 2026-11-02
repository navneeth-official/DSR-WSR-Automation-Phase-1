"""Jira story rows for monthly accomplishments summarization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Connection, text

from monthly_report.metrics import story_category


@dataclass(frozen=True)
class StoryRecord:
    jira_key: str
    summary: str
    title: str | None
    description: str | None
    status: str
    sprint_name: str | None
    story_points: float | None
    category: str


def stories_in_period(
    conn: Connection,
    project_id: int,
    period_start: date,
    period_end: date,
) -> list[StoryRecord]:
    """
    Stories on sprints overlapping the report period, one row per ``jira_key``.

    When multiple snapshot rows exist for the same key, keep the row with the latest
    ``updated_date`` (then ``snapshot_date``).
    """
    rows = conn.execute(
        text(
            """
            SELECT js.jira_key, js.summary, js.title, js.description, js.status,
                   js.story_points, s.sprint_name, js.updated_date, js.snapshot_date
            FROM jira_stories js
            LEFT JOIN sprints s ON s.sprint_id = js.sprint_id
            WHERE js.project_id = :project_id
              AND js.sprint_id IS NOT NULL
              AND s.sprint_start_date <= :period_end
              AND s.sprint_end_date >= :period_start
            ORDER BY js.jira_key, js.updated_date DESC NULLS LAST,
                     js.snapshot_date DESC NULLS LAST
            """
        ),
        {"project_id": project_id, "period_start": period_start, "period_end": period_end},
    ).all()

    by_key: dict[str, StoryRecord] = {}
    for (
        jira_key,
        summary,
        title,
        description,
        status,
        story_points,
        sprint_name,
        _updated,
        _snapshot,
    ) in rows:
        if jira_key in by_key:
            continue
        points = float(story_points) if story_points is not None else None
        by_key[jira_key] = StoryRecord(
            jira_key=jira_key,
            summary=summary or "",
            title=title,
            description=description,
            status=status or "",
            sprint_name=sprint_name,
            story_points=points,
            category=story_category(status),
        )

    return sorted(by_key.values(), key=lambda story: story.jira_key)
