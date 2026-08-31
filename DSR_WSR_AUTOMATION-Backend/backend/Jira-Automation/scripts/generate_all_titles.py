"""
Backfill missing story titles in jira_stories via GPT.

Usage:
    python scripts/generate_all_titles.py
    python scripts/generate_all_titles.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.repositories.jira_story_repository import JiraStoryRepository
from app.services.title_generator import TitleGenerationError, generate_and_assign_title


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate missing GPT titles for all stories in the database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List stories missing titles without calling GPT or saving.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        repo = JiraStoryRepository(db)
        stories = repo.get_all_latest()
        missing = [s for s in stories if not (s.title and s.title.strip())]

        if not missing:
            print("All stories already have titles.")
            return

        print(f"Found {len(missing)} stories without titles.")
        if args.dry_run:
            for story in missing:
                print(f"  - {story.jira_key}")
            return

        generated = 0
        for story in missing:
            try:
                if generate_and_assign_title(story):
                    db.commit()
                    generated += 1
                    print(f"  Generated: {story.jira_key} -> {story.title}")
            except TitleGenerationError as exc:
                db.rollback()
                print(f"Error: {exc}")
                raise SystemExit(1) from exc

        print(f"Done. Generated {generated} title(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
