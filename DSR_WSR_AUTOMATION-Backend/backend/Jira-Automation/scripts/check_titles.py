"""Quick check: how many stories have titles in the database."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal


def main() -> None:
    settings = get_settings()
    print(f"Database: {settings.database_url.split('@')[-1]}")

    db = SessionLocal()
    try:
        total = db.execute(text("SELECT COUNT(*) FROM jira_stories")).scalar()
        with_title = db.execute(
            text(
                "SELECT COUNT(*) FROM jira_stories "
                "WHERE title IS NOT NULL AND LENGTH(TRIM(title)) > 0"
            )
        ).scalar()
        null_title = total - with_title
        print(f"Total stories:  {total}")
        print(f"With title:     {with_title}")
        print(f"Null/empty:     {null_title}")
        print()
        print("Sample rows:")
        rows = db.execute(
            text(
                "SELECT jira_key, LEFT(summary, 40) AS summary, title "
                "FROM jira_stories ORDER BY jira_key LIMIT 10"
            )
        ).fetchall()
        for row in rows:
            print(f"  {row[0]} | title={row[2]!r}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
