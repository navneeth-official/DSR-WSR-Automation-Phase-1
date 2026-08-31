"""Composite primary key on jira_stories (jira_key, snapshot_date).

Revision ID: 010_composite_jira_story_pk
Revises:
Create Date: 2026-07-30

Note: Some environments applied this via scripts/apply_migration_010.py before
this revision file was added to the repo. Upgrade is a no-op when already applied.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010_composite_jira_story_pk"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    pk = bind.execute(
        sa.text(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            WHERE t.relname = 'jira_stories' AND c.contype = 'p'
            """
        )
    ).scalar()
    if pk and "snapshot_date" in pk:
        return

    op.execute(
        sa.text(
            """
            UPDATE jira_stories
            SET snapshot_date = COALESCE(snapshot_date, updated_date, created_date, CURRENT_DATE)
            WHERE snapshot_date IS NULL
            """
        )
    )
    op.execute(sa.text("ALTER TABLE jira_stories ALTER COLUMN snapshot_date SET NOT NULL"))
    op.execute(sa.text("ALTER TABLE jira_stories DROP CONSTRAINT jira_stories_pkey"))
    op.execute(
        sa.text(
            "ALTER TABLE jira_stories "
            "ADD CONSTRAINT jira_stories_pkey PRIMARY KEY (jira_key, snapshot_date)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_jira_stories_project_id_snapshot_date "
            "ON jira_stories (project_id, snapshot_date)"
        )
    )


def downgrade() -> None:
    pass
