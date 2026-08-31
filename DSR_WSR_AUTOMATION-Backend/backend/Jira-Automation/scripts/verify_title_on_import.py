"""Verify that upsert auto-generates and persists story titles."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import SessionLocal
from app.repositories.jira_story_repository import JiraStoryRepository
from app.services.rovo_import import map_rovo_item_to_story_fields

SAMPLE = Path(__file__).resolve().parents[1] / "sample rovo response.json"
TEST_KEY = "LOC-2750"


def main() -> None:
    with SAMPLE.open(encoding="utf-8") as f:
        payload = json.load(f)

    item = next(row for row in payload if row["jira_key"] == TEST_KEY)
    fields = map_rovo_item_to_story_fields(item)

    db = SessionLocal()
    try:
        repo = JiraStoryRepository(db)
        story = repo.upsert(**fields)

        print(f"Story:     {story.jira_key}")
        print(f"Summary:   {story.summary[:80]}...")
        print(f"Title:     {story.title}")
        print(f"Has title: {bool(story.title and story.title.strip())}")

        row = db.execute(
            text(
                "SELECT title FROM jira_stories WHERE jira_key = :key"
            ),
            {"key": TEST_KEY},
        ).fetchone()
        print(f"DB title:  {row[0] if row else None}")

        if not story.title or not story.title.strip():
            raise SystemExit("FAIL: title was not generated on insert")
        if row is None or not row[0]:
            raise SystemExit("FAIL: title not persisted in database")

        print("PASS: title auto-generated and saved on upsert.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
