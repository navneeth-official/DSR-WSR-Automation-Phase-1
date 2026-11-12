from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from sqlalchemy import text

from monthly_report.db import get_engine
from monthly_report.stories import stories_in_period


def main() -> None:
    period_start, period_end = date(2026, 10, 1), date(2026, 10, 31)
    with get_engine().connect() as conn:
        projs = conn.execute(
            text(
                """
                SELECT project_id, project_key, project_name
                FROM projects
                WHERE LOWER(project_name) LIKE :pattern
                   OR LOWER(project_key) LIKE :key_pattern
                """
            ),
            {"pattern": "%enter%", "key_pattern": "%ent%"},
        ).all()
        print("projects:", projs)
        for project_id, project_key, project_name in projs:
            rows = stories_in_period(conn, project_id, period_start, period_end)
            print(f"\n=== {project_name} ({project_key}) stories={len(rows)} ===")
            for story in rows:
                label = (story.title or story.summary).replace("\n", " ")
                print(
                    story.jira_key,
                    "|",
                    story.status,
                    "|",
                    story.category,
                    "|",
                    label[:160],
                )


if __name__ == "__main__":
    main()
