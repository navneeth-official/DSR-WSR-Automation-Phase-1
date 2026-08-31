"""One-off: check PK and run migration 010 if needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.database import engine

with engine.connect() as conn:
    rows = conn.execute(
        text(
            """
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'jira_stories' AND c.contype = 'p'
            """
        )
    ).all()
    print("Current PK:", rows)

    version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print("Alembic version:", version)
