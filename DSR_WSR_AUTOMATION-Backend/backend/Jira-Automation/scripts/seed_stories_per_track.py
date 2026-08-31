"""
Seed at least N stories per track (project) with different assignees.

Uses active employees from employee_tracks when available; otherwise falls back
to the WSR seed assignee catalog. Re-runs backfill_employees_from_stories after insert.

Usage:
    python scripts/seed_stories_per_track.py
    python scripts/seed_stories_per_track.py --min-stories 3 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models.employee  # noqa: F401
import app.models.jira_story  # noqa: F401
import app.models.project  # noqa: F401
import app.models.sprint  # noqa: F401
import app.models.team  # noqa: F401

from app.database import SessionLocal
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.jira_story_repository import JiraStoryRepository
from app.repositories.project_repository import ProjectRepository
from app.services.rovo_import import import_rovo_payload

# Fallback assignees per project_key (from WSR seed catalog + extras).
FALLBACK_ASSIGNEES: dict[str, list[str]] = {
    "COST": ["Rishi Manoj", "Danny Baggett", "Priya Nambiar"],
    "LOC": ["Vignesh Krishnan", "Vineed Kaladharan", "Suraj Seshadri"],
    "PRC": ["Ananya Mehta", "Kevin Loh", "Tom Alves"],
    "PRICE": ["Ananya Mehta", "Kevin Loh", "VijaiKrishna CherucattuVidyadharan"],
    "SUP": ["Laura Chen", "Miguel Santos", "Priya Nambiar"],
    "SPUR": ["Tom Alves", "Priya Nambiar", "James Park"],
    "WNF": ["James Park", "Sara Kim", "Laura Chen"],
    "GSS": ["Sara Kim", "Miguel Santos", "Vignesh Krishnan"],
    "PHRM": ["Vineed Kaladharan", "Ananya Mehta", "Rishi Manoj"],
    "PATRV": ["Vignesh Krishnan", "Vineed Kaladharan", "Suraj Seshadri"],
}

DEFAULT_SPRINT = {
    "sprint_name": "Q3.04 FY26 Andromeda",
    "sprint_start_date": "2026-07-14",
    "sprint_end_date": "2026-07-27",
}

SNAPSHOT_DATE = date(2026, 7, 31)

SUMMARY_TEMPLATES = [
    "Implement {feature} for {track} track",
    "Fix regression in {feature} ({track})",
    "Add test coverage for {feature} ({track})",
]

FEATURES = [
    "catalog sync",
    "ledger export",
    "API validation",
    "batch reconciliation",
    "onboarding workflow",
]


def _assignees_for_project(
    employees_repo: EmployeeRepository,
    project_id: int,
    project_key: str,
    min_count: int,
) -> list[str]:
    assignments = employees_repo.list_employees_for_track(project_id, active_only=True)
    names: list[str] = []
    seen: set[str] = set()
    for row in assignments:
        name = row.employee.employee_name.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    fallbacks = FALLBACK_ASSIGNEES.get(project_key.upper(), [])
    for name in fallbacks:
        if name not in seen:
            seen.add(name)
            names.append(name)

    while len(names) < min_count:
        synthetic = f"{project_key} Developer {len(names) + 1}"
        if synthetic not in seen:
            seen.add(synthetic)
            names.append(synthetic)

    return names[:max(min_count, len(names))]


def build_rows_for_project(
    *,
    project_key: str,
    project_name: str,
    assignees: list[str],
    min_stories: int,
    story_repo: JiraStoryRepository,
) -> list[dict]:
    rows: list[dict] = []
    snap = SNAPSHOT_DATE.isoformat()

    for i in range(min_stories):
        assignee = assignees[i % len(assignees)]
        key_suffix = 7000 + i + 1
        jira_key = f"{project_key}-DEMO{key_suffix}"
        if story_repo.story_exists(jira_key):
            continue

        feature = FEATURES[i % len(FEATURES)]
        template = SUMMARY_TEMPLATES[i % len(SUMMARY_TEMPLATES)]
        summary = template.format(feature=feature, track=project_key)
        status = ["To Do", "In Progress", "Done"][i % 3]

        rows.append(
            {
                "project_key": project_key,
                "project_name": project_name,
                **DEFAULT_SPRINT,
                "jira_key": jira_key,
                "summary": summary,
                "description": (
                    f"Demo seed story {i + 1} for {project_name} "
                    f"assigned to {assignee}."
                ),
                "issue_type": "Bug" if i % 2 else "Story",
                "priority": ["Low", "Medium", "High"][i % 3],
                "assignee": assignee,
                "reporter": assignees[(i + 1) % len(assignees)],
                "status": status,
                "story_points": (i % 5) + 1,
                "created_date": "2026-07-01",
                "updated_date": snap,
                "resolved_date": snap if status == "Done" else None,
                "snapshot_date": snap,
            }
        )

    return rows


def seed_stories_per_track(
    *,
    min_stories: int = 3,
    dry_run: bool = False,
) -> None:
    db = SessionLocal()
    projects_repo = ProjectRepository(db)
    employees_repo = EmployeeRepository(db)
    story_repo = JiraStoryRepository(db)

    projects = projects_repo.get_all()
    all_rows: list[dict] = []

    print(f"Tracks in database: {len(projects)}")
    for project in projects:
        assignees = _assignees_for_project(
            employees_repo,
            project.project_id,
            project.project_key,
            min_stories,
        )
        rows = build_rows_for_project(
            project_key=project.project_key,
            project_name=project.project_name,
            assignees=assignees[:min_stories],
            min_stories=min_stories,
            story_repo=story_repo,
        )
        if rows:
            print(
                f"  {project.project_key}: {len(rows)} new stories "
                f"({', '.join(r['assignee'] for r in rows)})"
            )
        else:
            print(f"  {project.project_key}: all DEMO keys already exist — skipping")
        all_rows.extend(rows)

    print(f"\nTotal new story rows: {len(all_rows)}")

    if dry_run:
        print("Dry run — no database changes.")
        db.close()
        return

    if not all_rows:
        print("Nothing to insert.")
        db.close()
        return

    keys = import_rovo_payload(story_repo, all_rows)
    db.close()

    print(f"Inserted {len(all_rows)} rows for {len(set(keys))} jira keys.")

    import subprocess

    backfill_script = Path(__file__).resolve().parent / "backfill_employees_from_stories.py"
    print("\nSyncing employees from stories …")
    subprocess.run([sys.executable, str(backfill_script)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed demo stories per track with distinct assignees.",
    )
    parser.add_argument(
        "--min-stories",
        type=int,
        default=3,
        help="Stories to ensure per track (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without writing",
    )
    args = parser.parse_args()

    if args.min_stories < 1:
        print("--min-stories must be at least 1")
        sys.exit(1)

    seed_stories_per_track(min_stories=args.min_stories, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
