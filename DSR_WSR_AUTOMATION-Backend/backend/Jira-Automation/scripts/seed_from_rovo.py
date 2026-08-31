"""
Import Rovo AI JSON response into jira_stories table.

Usage:
    python scripts/seed_from_rovo.py path/to/Rovo_JSON_Response.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.repositories.jira_story_repository import JiraStoryRepository
from app.services.rovo_import import import_rovo_payload
from app.services.title_generator import TitleGenerationError


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_from_rovo.py <rovo-json-file>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
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
        repo = JiraStoryRepository(db)
        keys = import_rovo_payload(repo, payload)
        print(f"Imported {len(keys)} stories: {', '.join(keys)}")
    except TitleGenerationError as exc:
        print(f"Import failed — title generation error: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
