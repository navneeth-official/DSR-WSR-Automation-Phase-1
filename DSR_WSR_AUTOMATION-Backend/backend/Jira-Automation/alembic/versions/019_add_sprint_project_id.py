"""Give each sprint row the project it belongs to.

Older databases stored one sprint row and pointed stories from several projects
at it. The app model is one sprint per (project, sprint name). Existing rows
keep the lowest project id; other projects get a copied sprint row, and their
stories are repointed.

Revision ID: 019_add_sprint_project_id
Revises: 018_story_status_lookup
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "019_add_sprint_project_id"
down_revision: Union[str, None] = "018_story_status_lookup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in inspect(bind).get_columns("sprints")}
    if "project_id" in cols:
        return

    op.execute(sa.text("ALTER TABLE sprints DROP CONSTRAINT IF EXISTS uq_sprints_sprint_name"))
    op.add_column("sprints", sa.Column("project_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE sprints AS s
            SET project_id = sub.project_id
            FROM (
                SELECT sprint_id, MIN(project_id) AS project_id
                FROM jira_stories
                WHERE sprint_id IS NOT NULL
                GROUP BY sprint_id
            ) AS sub
            WHERE s.sprint_id = sub.sprint_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                rec RECORD;
                new_id INTEGER;
            BEGIN
                FOR rec IN
                    SELECT DISTINCT j.sprint_id AS old_sprint_id, j.project_id
                    FROM jira_stories AS j
                    JOIN sprints AS s ON s.sprint_id = j.sprint_id
                    WHERE j.project_id <> s.project_id
                LOOP
                    SELECT COALESCE(MAX(sprint_id), 0) + 1 INTO new_id FROM sprints;

                    INSERT INTO sprints (
                        sprint_id,
                        sprint_name,
                        sprint_start_date,
                        sprint_end_date,
                        created_at,
                        updated_at,
                        sprint_status,
                        project_id
                    )
                    SELECT
                        new_id,
                        sprint_name,
                        sprint_start_date,
                        sprint_end_date,
                        created_at,
                        updated_at,
                        sprint_status,
                        rec.project_id
                    FROM sprints
                    WHERE sprint_id = rec.old_sprint_id;

                    UPDATE jira_stories
                    SET sprint_id = new_id
                    WHERE sprint_id = rec.old_sprint_id
                      AND project_id = rec.project_id;
                END LOOP;
            END $$;
            """
        )
    )
    leftover = bind.execute(
        sa.text("SELECT COUNT(*) FROM sprints WHERE project_id IS NULL")
    ).scalar()
    if leftover:
        raise RuntimeError(
            f"{leftover} sprint row(s) have no project_id after the split."
        )

    op.alter_column("sprints", "project_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_sprints_project_id",
        "sprints",
        "projects",
        ["project_id"],
        ["project_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_sprints_project_id", "sprints", ["project_id"])
    op.create_unique_constraint(
        "uq_sprints_project_name",
        "sprints",
        ["project_id", "sprint_name"],
    )
    bind.execute(
        sa.text(
            """
            SELECT setval(
                pg_get_serial_sequence('sprints', 'sprint_id'),
                (SELECT MAX(sprint_id) FROM sprints)
            )
            WHERE pg_get_serial_sequence('sprints', 'sprint_id') IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("uq_sprints_project_name", "sprints", type_="unique")
    op.drop_index("ix_sprints_project_id", table_name="sprints")
    op.drop_constraint("fk_sprints_project_id", "sprints", type_="foreignkey")
    op.drop_column("sprints", "project_id")
