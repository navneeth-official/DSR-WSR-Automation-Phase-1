"""
Backfill employees and employee_tracks from assignees on existing jira_stories rows.

Creates one employee per distinct assignee name (under the default team) and links
each employee to every project (track) they appear on in the stories table.

Usage:
    python scripts/backfill_employees_from_stories.py
    python scripts/backfill_employees_from_stories.py --dry-run
    python scripts/backfill_employees_from_stories.py --team HEB
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models.employee  # noqa: F401
import app.models.jira_story  # noqa: F401
import app.models.project  # noqa: F401
import app.models.sprint  # noqa: F401
import app.models.team  # noqa: F401

from sqlalchemy import distinct, select

from app.constants.teams import DEFAULT_TEAM_NAME, KNOWN_TEAM_NAMES
from app.database import SessionLocal
from app.models.jira_story import JiraStory
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.project_repository import ProjectRepository


def _distinct_assignee_project_pairs(db) -> list[tuple[str, int]]:
    rows = db.execute(
        select(distinct(JiraStory.assignee), JiraStory.project_id)
        .where(JiraStory.assignee.isnot(None))
        .where(JiraStory.assignee != "")
    ).all()
    pairs: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for assignee, project_id in rows:
        name = (assignee or "").strip()
        if not name or project_id is None:
            continue
        key = (name, int(project_id))
        if key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    return sorted(pairs, key=lambda x: (x[1], x[0]))


def backfill_employees_from_stories(
    *,
    team_name: str = DEFAULT_TEAM_NAME,
    dry_run: bool = False,
) -> None:
    normalized_team = team_name.strip()
    if normalized_team not in KNOWN_TEAM_NAMES:
        raise ValueError(f"Unknown team '{team_name}'. Known: {sorted(KNOWN_TEAM_NAMES)}")

    db = SessionLocal()
    employees_repo = EmployeeRepository(db)
    projects_repo = ProjectRepository(db)

    team = employees_repo.get_team_by_name(normalized_team)
    if team is None:
        raise RuntimeError(
            f"Team '{normalized_team}' not found. Run scripts/apply_employees_migration.py first."
        )

    pairs = _distinct_assignee_project_pairs(db)
    if not pairs:
        print("No assignees found on jira_stories.")
        return

    print(f"Found {len(pairs)} distinct assignee + track pairs in jira_stories.")

    created_employees = 0
    created_assignments = 0
    reactivated_assignments = 0
    skipped = 0

    employee_cache: dict[str, int] = {}

    for assignee_name, project_id in pairs:
        project = projects_repo.get_by_id(project_id)
        if project is None:
            print(f"  skip: project_id={project_id} not found for assignee {assignee_name!r}")
            skipped += 1
            continue

        if dry_run:
            print(f"  would link {assignee_name!r} -> {project.project_key} ({project_id})")
            continue

        if assignee_name not in employee_cache:
            existing = employees_repo.get_employee_by_name(team.team_id, assignee_name)
            if existing is None:
                employee = employees_repo.create_employee(
                    employee_name=assignee_name,
                    team_id=team.team_id,
                )
                created_employees += 1
                employee_cache[assignee_name] = employee.employee_id
            else:
                employee_cache[assignee_name] = existing.employee_id

        employee_id = employee_cache[assignee_name]
        assignment = employees_repo.get_track_assignment(employee_id, project_id)
        if assignment is None:
            employees_repo.add_track_assignment(
                employee_id=employee_id,
                project_id=project_id,
                is_active=True,
            )
            created_assignments += 1
        elif not assignment.is_active:
            employees_repo.update_track_assignment(assignment, is_active=True)
            reactivated_assignments += 1

    if dry_run:
        print(f"Dry run complete — {len(pairs)} pairs would be processed.")
        return

    print(
        f"Backfill complete: "
        f"{created_employees} employees created, "
        f"{created_assignments} track assignments created, "
        f"{reactivated_assignments} assignments reactivated, "
        f"{skipped} skipped."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate employees / employee_tracks from jira_stories assignees.",
    )
    parser.add_argument(
        "--team",
        default=DEFAULT_TEAM_NAME,
        help=f"Team/account name (default: {DEFAULT_TEAM_NAME})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing to the database",
    )
    args = parser.parse_args()
    backfill_employees_from_stories(team_name=args.team, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
