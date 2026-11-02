"""Fetch projects, sprints and story statuses for a monthly report period."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Connection, text


@dataclass(frozen=True)
class Project:
    project_id: int
    project_key: str
    project_name: str


@dataclass(frozen=True)
class SprintStories:
    sprint_id: int
    sprint_name: str
    sprint_status: str | None
    start_date: date
    end_date: date
    story_statuses: tuple[str, ...]


def month_bounds(day: date) -> tuple[date, date]:
    last_day = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last_day)


def find_project(conn: Connection, project: str) -> Project:
    """Look up a project by key (PRC) or name (Pricing), case-insensitive."""
    row = conn.execute(
        text(
            """
            SELECT project_id, project_key, project_name
            FROM projects
            WHERE lower(project_key) = lower(:project)
               OR lower(project_name) = lower(:project)
            """
        ),
        {"project": project},
    ).first()
    if row is None:
        available = conn.execute(
            text("SELECT project_key, project_name FROM projects ORDER BY project_key")
        ).all()
        listing = ", ".join(f"{key} ({name})" for key, name in available)
        raise LookupError(f"Unknown project {project!r}. Available: {listing}")
    return Project(*row)


def list_projects_with_sprints_in_period(
    conn: Connection,
    period_start: date,
    period_end: date,
) -> list[Project]:
    """Distinct projects that have at least one story in a sprint overlapping the period."""
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT p.project_id, p.project_key, p.project_name
            FROM projects p
            JOIN jira_stories js ON js.project_id = p.project_id
            JOIN sprints s ON s.sprint_id = js.sprint_id
            WHERE s.sprint_start_date <= :period_end
              AND s.sprint_end_date >= :period_start
            ORDER BY p.project_key
            """
        ),
        {"period_start": period_start, "period_end": period_end},
    ).all()
    return [Project(*row) for row in rows]


def order_projects(projects: list[Project], order_keys: list[str]) -> list[Project]:
    rank = {key: index for index, key in enumerate(order_keys)}
    return sorted(
        projects,
        key=lambda project: (rank.get(project.project_key, len(rank) + 100), project.project_key),
    )


def sprints_in_period(
    conn: Connection,
    project_id: int,
    period_start: date,
    period_end: date,
) -> list[SprintStories]:
    """Sprints overlapping the period that have stories for the project, oldest first."""
    rows = conn.execute(
        text(
            """
            SELECT s.sprint_id, s.sprint_name, s.sprint_status,
                   s.sprint_start_date, s.sprint_end_date, js.status
            FROM jira_stories js
            JOIN sprints s ON s.sprint_id = js.sprint_id
            WHERE js.project_id = :project_id
              AND s.sprint_start_date <= :period_end
              AND s.sprint_end_date >= :period_start
            ORDER BY s.sprint_start_date, s.sprint_end_date, s.sprint_name, js.jira_key
            """
        ),
        {"project_id": project_id, "period_start": period_start, "period_end": period_end},
    ).all()

    sprints: dict[int, dict] = {}
    for sprint_id, name, status, start, end, story_status in rows:
        entry = sprints.setdefault(
            sprint_id,
            {"name": name, "status": status, "start": start, "end": end, "stories": []},
        )
        entry["stories"].append(story_status)

    return [
        SprintStories(
            sprint_id=sprint_id,
            sprint_name=entry["name"],
            sprint_status=entry["status"],
            start_date=entry["start"],
            end_date=entry["end"],
            story_statuses=tuple(entry["stories"]),
        )
        for sprint_id, entry in sprints.items()
    ]
