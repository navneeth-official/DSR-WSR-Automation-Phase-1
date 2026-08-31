"""
Wipe jira_stories and sprints, then import a Rovo JSON array.

Projects are left intact; missing project_keys are created via get_or_create.

Usage:
    python scripts/reset_and_seed_stories.py [path/to/stories.json]

Default JSON: data/july27_stories.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import SessionLocal
from app.repositories.jira_story_repository import JiraStoryRepository
from app.services.rovo_import import import_rovo_payload
from app.services.title_generator import TitleGenerationError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "data" / "july27_stories.json"


def wipe_stories_and_sprints(db) -> tuple[int, int]:
    """Delete all story rows then sprint rows (FK-safe order)."""
    stories_deleted = db.execute(text("DELETE FROM jira_stories")).rowcount or 0
    sprints_deleted = db.execute(text("DELETE FROM sprints")).rowcount or 0
    db.commit()
    return int(stories_deleted), int(sprints_deleted)


def list_projects(db) -> list[tuple[str, str]]:
    rows = db.execute(
        text("SELECT project_key, project_name FROM projects ORDER BY project_key")
    ).all()
    return [(str(k), str(n)) for k, n in rows]


def main() -> None:
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JSON
    if not json_path.exists():
        print(f"File not found: {json_path}")
        sys.exit(1)

    with json_path.open(encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, list):
        print("Expected a JSON array of Jira story objects.")
        sys.exit(1)

    db = SessionLocal()
    try:
        projects_before = list_projects(db)
        print(f"Projects before ({len(projects_before)}): {', '.join(k for k, _ in projects_before)}")

        deleted_stories, deleted_sprints = wipe_stories_and_sprints(db)
        print(f"Deleted {deleted_stories} jira_stories rows and {deleted_sprints} sprints rows.")

        repo = JiraStoryRepository(db)
        keys = import_rovo_payload(repo, payload)
        print(f"Imported {len(keys)} stories.")

        projects_after = list_projects(db)
        new_keys = {k for k, _ in projects_after} - {k for k, _ in projects_before}
        if new_keys:
            print(f"New projects added: {', '.join(sorted(new_keys))}")
        else:
            print("No new projects added (existing tracks reused).")

        story_count = db.execute(text("SELECT COUNT(*) FROM jira_stories")).scalar()
        sprint_count = db.execute(text("SELECT COUNT(*) FROM sprints")).scalar()
        print(f"Final counts — stories: {story_count}, sprints: {sprint_count}, projects: {len(projects_after)}")
        print("Keys:", ", ".join(keys))
    except TitleGenerationError as exc:
        print(f"Import failed — title generation error: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
