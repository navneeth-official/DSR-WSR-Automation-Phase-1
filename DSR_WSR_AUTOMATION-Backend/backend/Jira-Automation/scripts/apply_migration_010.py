"""Apply migration 010_composite_jira_story_pk if not already applied."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import engine

MIGRATION_SQL = [
    """
    UPDATE jira_stories
    SET snapshot_date = COALESCE(snapshot_date, updated_date, created_date, CURRENT_DATE)
    WHERE snapshot_date IS NULL
    """,
    """
    ALTER TABLE jira_stories
    ALTER COLUMN snapshot_date SET NOT NULL
    """,
    """
    ALTER TABLE jira_stories DROP CONSTRAINT jira_stories_pkey
    """,
    """
    ALTER TABLE jira_stories
    ADD CONSTRAINT jira_stories_pkey PRIMARY KEY (jira_key, snapshot_date)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_jira_stories_project_id_snapshot_date
    ON jira_stories (project_id, snapshot_date)
    """,
]


def main() -> None:
    with engine.begin() as conn:
        pk = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'jira_stories' AND c.contype = 'p'
                """
            )
        ).scalar()
        print("Before:", pk)
        if pk and "snapshot_date" in pk:
            print("Composite PK already applied.")
            return

        for stmt in MIGRATION_SQL:
            conn.execute(text(stmt))

        conn.execute(
            text("UPDATE alembic_version SET version_num = '010_composite_jira_story_pk'")
        )

        pk_after = conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'jira_stories' AND c.contype = 'p'
                """
            )
        ).scalar()
        print("After:", pk_after)
        print("Migration 010 applied.")


if __name__ == "__main__":
    main()
