"""Make projects.team_id nullable so auto-created projects work without a team row."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import engine


def main() -> None:
    with engine.begin() as conn:
        column = conn.execute(
            text(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'projects'
                  AND column_name = 'team_id'
                """
            )
        ).scalar()

        if column is None:
            print("projects.team_id column not found — nothing to change.")
            return

        if column == "YES":
            print("projects.team_id is already nullable.")
            return

        conn.execute(
            text("ALTER TABLE projects ALTER COLUMN team_id DROP NOT NULL")
        )
        print("projects.team_id is now nullable.")


if __name__ == "__main__":
    main()
