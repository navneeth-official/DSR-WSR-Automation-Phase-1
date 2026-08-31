import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import engine

with engine.connect() as c:
    for key in ("SUP", "WNF"):
        print(f"\n{key} sprints from existing stories:")
        rows = c.execute(
            text(
                """
                SELECT DISTINCT s.sprint_id, s.sprint_name, s.project_id
                FROM sprints s
                JOIN jira_stories j ON j.sprint_id = s.sprint_id
                JOIN projects p ON j.project_id = p.project_id
                WHERE p.project_key = :key
                ORDER BY s.sprint_id
                LIMIT 5
                """
            ),
            {"key": key},
        )
        for row in rows:
            print(row)
