"""
Seed many WSR-ready stories across all tracks with June/July 2026 snapshot dates.

Creates stories in Q3 sprints (June–July) for every track, with multiple snapshot
rows per story so WSR/DSR queries have rich data to work with.

Usage:
    python scripts/seed_wsr_june_july_stories.py
    python scripts/seed_wsr_june_july_stories.py --stories-per-sprint 10
    python scripts/seed_wsr_june_july_stories.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.repositories.jira_story_repository import JiraStoryRepository
from app.services.rovo_import import import_rovo_payload

SNAPSHOT_DATES = [
    date(2026, 6, 11),
    date(2026, 6, 20),
    date(2026, 7, 7),
    date(2026, 7, 14),
    date(2026, 7, 15),
    date(2026, 7, 16),
]

JUNE_JULY_SPRINTS = [
    {
        "sprint_name": "Q3.01 FY26 Phoenix",
        "sprint_start_date": "2026-06-01",
        "sprint_end_date": "2026-06-15",
    },
    {
        "sprint_name": "Q3.02 FY26 Orion",
        "sprint_start_date": "2026-06-16",
        "sprint_end_date": "2026-06-29",
    },
    {
        "sprint_name": "Q3.03 FY26 Centaurus",
        "sprint_start_date": "2026-06-30",
        "sprint_end_date": "2026-07-13",
    },
    {
        "sprint_name": "Q3.04 FY26 Andromeda",
        "sprint_start_date": "2026-07-14",
        "sprint_end_date": "2026-07-27",
    },
]

TRACKS = [
    {
        "project_key": "COST",
        "project_name": "Cost Core Service",
        "assignees": ["Rishi Manoj", "Danny Baggett", "Priya Nambiar"],
        "reporters": ["Danny Baggett", "Kevin Loh"],
        "key_base": 6100,
    },
    {
        "project_key": "LOC",
        "project_name": "LOCO",
        "assignees": ["Vignesh Krishnan", "Vineed Kaladharan", "Suraj Seshadri"],
        "reporters": ["Suraj Seshadri", "Vinu Lilitha"],
        "key_base": 6100,
    },
    {
        "project_key": "PRC",
        "project_name": "Pricing Core Service",
        "assignees": ["Ananya Mehta", "Kevin Loh", "Tom Alves"],
        "reporters": ["Kevin Loh", "Ananya Mehta"],
        "key_base": 6100,
    },
    {
        "project_key": "SUP",
        "project_name": "Supplier Core Service",
        "assignees": ["Laura Chen", "Miguel Santos", "Priya Nambiar"],
        "reporters": ["Miguel Santos", "Laura Chen"],
        "key_base": 6100,
    },
    {
        "project_key": "SPUR",
        "project_name": "Supplier Core Service – SPUR",
        "assignees": ["Tom Alves", "Priya Nambiar", "James Park"],
        "reporters": ["Tom Alves", "Priya Nambiar"],
        "key_base": 6100,
    },
    {
        "project_key": "WNF",
        "project_name": "Wentforth",
        "assignees": ["James Park", "Sara Kim", "Laura Chen"],
        "reporters": ["Sara Kim", "James Park"],
        "key_base": 6100,
    },
    {
        "project_key": "GSS",
        "project_name": "GSS",
        "assignees": ["Sara Kim", "Miguel Santos", "Vignesh Krishnan"],
        "reporters": ["Miguel Santos", "Sara Kim"],
        "key_base": 6100,
    },
    {
        "project_key": "PHRM",
        "project_name": "Pharamacy",
        "assignees": ["Vineed Kaladharan", "Ananya Mehta", "Rishi Manoj"],
        "reporters": ["Vinu Lilitha", "Ananya Mehta"],
        "key_base": 6100,
    },
]

STORY_TEMPLATES = [
    "Implement {feature} API endpoint for {track}",
    "Fix validation issue in {feature} workflow ({track})",
    "Add unit tests for {feature} service layer",
    "Refactor {feature} data access for performance",
    "Update {feature} acceptance criteria per BSA review",
    "Investigate production timeout on {feature} endpoint",
    "Backfill historical data for {feature} pipeline",
    "Deprecate legacy {feature} integration path",
    "Add monitoring alerts for {feature} batch job",
    "Document {feature} rollout and rollback steps",
    "Handle edge case in {feature} reconciliation logic",
    "Align {feature} schema with downstream consumers",
]

FEATURES = [
    "catalog sync",
    "ledger export",
    "warehouse audit",
    "pricing proposal",
    "supplier onboarding",
    "cost reconciliation",
    "inventory adjustment",
    "contract transition",
    "offsite warehouse",
    "loyalty export",
]


def _status_for_snapshot(snap_idx: int, story_idx: int) -> str:
    """Vary status across snapshots and stories."""
    phase = (snap_idx + story_idx) % 6
    if phase <= 1:
        return "To Do"
    if phase <= 3:
        return "In Progress"
    return "Done"


def build_payload(*, stories_per_sprint: int) -> list[dict]:
    rows: list[dict] = []
    story_counter = 0

    for track in TRACKS:
        pk = track["project_key"]
        for sprint_idx, sprint in enumerate(JUNE_JULY_SPRINTS):
            for i in range(stories_per_sprint):
                story_counter += 1
                key_num = track["key_base"] + sprint_idx * 100 + i + 1
                jira_key = f"{pk}-{key_num}"
                feature = FEATURES[(story_counter + i) % len(FEATURES)]
                template = STORY_TEMPLATES[(story_counter + sprint_idx) % len(STORY_TEMPLATES)]
                summary = template.format(feature=feature, track=pk)
                title = f"Update {feature} for {pk} track"
                assignee = track["assignees"][i % len(track["assignees"])]
                reporter = track["reporters"][i % len(track["reporters"])]
                issue_type = "Bug" if i % 4 == 0 else "Story"
                points = (i % 5) + 1
                created = date(2026, 6, 1 + (i % 10))

                for snap_idx, snap in enumerate(SNAPSHOT_DATES):
                    status = _status_for_snapshot(snap_idx, i)
                    rows.append(
                        {
                            "project_key": pk,
                            "project_name": track["project_name"],
                            **sprint,
                            "jira_key": jira_key,
                            "summary": summary,
                            "title": title,
                            "description": (
                                f"WSR seed story for {pk} / {sprint['sprint_name']} "
                                f"(snapshot {snap.isoformat()})."
                            ),
                            "issue_type": issue_type,
                            "priority": ["Low", "Medium", "High"][i % 3],
                            "assignee": assignee,
                            "reporter": reporter,
                            "status": status,
                            "story_points": points,
                            "created_date": created.isoformat(),
                            "updated_date": snap.isoformat(),
                            "resolved_date": snap.isoformat() if status == "Done" else None,
                            "snapshot_date": snap.isoformat(),
                        }
                    )

    return rows


TRACK_PREFIXES = ("COST", "LOC", "PRC", "SUP", "SPUR", "WNF", "GSS", "PHRM")
SEED_KEY_PATTERN = r"^(" + "|".join(TRACK_PREFIXES) + r")-6[0-9]{3}$"


def delete_seeded_wsr_stories(db) -> int:
    """Remove bulk WSR seed rows (TRACK-6xxx keys)."""
    from sqlalchemy import text

    result = db.execute(
        text("DELETE FROM jira_stories WHERE jira_key ~ :pattern"),
        {"pattern": SEED_KEY_PATTERN},
    )
    db.commit()
    return int(result.rowcount or 0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed June/July WSR stories across all tracks and Q3 sprints."
    )
    parser.add_argument(
        "--stories-per-sprint",
        type=int,
        default=1,
        help="Number of unique stories per track per sprint (default: 1)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing TRACK-6xxx seed rows before inserting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not write to the database",
    )
    args = parser.parse_args()

    if args.stories_per_sprint < 1:
        print("--stories-per-sprint must be at least 1")
        sys.exit(1)

    payload = build_payload(stories_per_sprint=args.stories_per_sprint)
    unique_keys = len({row["jira_key"] for row in payload})
    unique_snaps = len(SNAPSHOT_DATES)

    print("WSR June/July seed plan")
    print(f"  Tracks:              {len(TRACKS)}")
    print(f"  Sprints per track:   {len(JUNE_JULY_SPRINTS)}")
    print(f"  Stories per sprint:  {args.stories_per_sprint}")
    print(f"  Snapshots per story: {unique_snaps}")
    print(f"  Unique jira keys:    {unique_keys}")
    print(f"  Total rows to upsert: {len(payload)}")
    print(f"  Snapshot dates:      {', '.join(d.isoformat() for d in SNAPSHOT_DATES)}")

    if args.dry_run:
        print("\nDry run — no database changes.")
        return

    db = SessionLocal()
    try:
        if args.reset:
            deleted = delete_seeded_wsr_stories(db)
            print(f"Deleted {deleted} existing seed rows.")
        repo = JiraStoryRepository(db)
        keys = import_rovo_payload(repo, payload)
    finally:
        db.close()

    print(f"\nSeeded {len(payload)} snapshot rows for {len(set(keys))} jira keys.")
    print("\nTry WSR generate for these weeks:")
    print("  POST /api/wsr/generate  start_date=2026-06-09  end_date=2026-06-13")
    print("  POST /api/wsr/generate  start_date=2026-06-16  end_date=2026-06-20")
    print("  POST /api/wsr/generate  start_date=2026-07-07  end_date=2026-07-11")
    print("  POST /api/wsr/generate  start_date=2026-07-14  end_date=2026-07-18")


if __name__ == "__main__":
    main()
