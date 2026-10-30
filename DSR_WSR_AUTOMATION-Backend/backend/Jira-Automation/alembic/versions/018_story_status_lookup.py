"""Replace jira_stories.status (text) with an integer FK to a story_statuses lookup.

Lookup rows (status_id -> status_name):
    1 To Do, 2 In Progress, 3 In Review, 4 Done, 5 Blocked

Existing free-text statuses are mapped onto those ids (case/separator
insensitive, e.g. "In-Progress", "in progress", "IN_PROGRESS" -> 2). Any legacy
text that cannot be mapped is set to "To Do" so the column can be NOT NULL. New
unmappable statuses are caught in the intake Review & Edit page (the user must pick
one from a dropdown) and rejected by the API. Downgrade restores the text column
using the lookup names (original spelling variants are not recoverable).

Revision ID: 018_story_status_lookup
Revises: 017_make_remya_pmo
Create Date: 2026-10-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "018_story_status_lookup"
down_revision: Union[str, None] = "017_make_remya_pmo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = (
    (1, "To Do"),
    (2, "In Progress"),
    (3, "In Review"),
    (4, "Done"),
    (5, "Blocked"),
)

# Normalised text (lower-case, separators collapsed to a space) -> status_id.
ALIASES = {
    "to do": 1,
    "todo": 1,
    "open": 1,
    "backlog": 1,
    "new": 1,
    "reopened": 1,
    "selected for development": 1,
    "in progress": 2,
    "inprogress": 2,
    "in development": 2,
    "wip": 2,
    "active": 2,
    "in review": 3,
    "inreview": 3,
    "review": 3,
    "code review": 3,
    "ready for qa": 3,
    "in qa": 3,
    "in testing": 3,
    "done": 4,
    "closed": 4,
    "resolved": 4,
    "complete": 4,
    "completed": 4,
    "blocked": 5,
    "on hold": 5,
    "impediment": 5,
}

NORMALIZED_STATUS_SQL = "lower(regexp_replace(btrim(status), '[\\s_-]+', ' ', 'g'))"


def _backfill_case_sql() -> str:
    whens = " ".join(
        f"WHEN {NORMALIZED_STATUS_SQL} = '{alias}' THEN {status_id}"
        for alias, status_id in ALIASES.items()
    )
    # Unrecognised legacy text falls back to "To Do" (id 1).
    return f"CASE {whens} ELSE 1 END"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "story_statuses" not in insp.get_table_names():
        op.create_table(
            "story_statuses",
            sa.Column("status_id", sa.Integer(), primary_key=True, autoincrement=False),
            sa.Column("status_name", sa.String(length=50), nullable=False),
            sa.UniqueConstraint("status_name", name="uq_story_statuses_status_name"),
        )

    statuses_table = sa.table(
        "story_statuses",
        sa.column("status_id", sa.Integer),
        sa.column("status_name", sa.String),
    )
    existing_ids = {row[0] for row in bind.execute(sa.text("SELECT status_id FROM story_statuses"))}
    missing = [
        {"status_id": status_id, "status_name": name}
        for status_id, name in STATUSES
        if status_id not in existing_ids
    ]
    if missing:
        op.bulk_insert(statuses_table, missing)

    cols = {col["name"] for col in insp.get_columns("jira_stories")}
    if "status_id" not in cols:
        op.add_column("jira_stories", sa.Column("status_id", sa.Integer(), nullable=True))

    if "status" in cols:
        op.execute(sa.text(f"UPDATE jira_stories SET status_id = {_backfill_case_sql()}"))
    op.execute(sa.text("UPDATE jira_stories SET status_id = 1 WHERE status_id IS NULL"))

    op.alter_column("jira_stories", "status_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "fk_jira_stories_status_id",
        "jira_stories",
        "story_statuses",
        ["status_id"],
        ["status_id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_jira_stories_status_id", "jira_stories", ["status_id"])

    if "status" in cols:
        # Dropping the column also drops its ix_jira_stories_status index.
        op.drop_column("jira_stories", "status")


def downgrade() -> None:
    op.add_column("jira_stories", sa.Column("status", sa.String(length=100), nullable=True))
    op.execute(
        sa.text(
            "UPDATE jira_stories SET status = ("
            "SELECT s.status_name FROM story_statuses s "
            "WHERE s.status_id = jira_stories.status_id)"
        )
    )
    op.execute(sa.text("UPDATE jira_stories SET status = 'To Do' WHERE status IS NULL"))
    op.alter_column("jira_stories", "status", existing_type=sa.String(length=100), nullable=False)
    op.create_index("ix_jira_stories_status", "jira_stories", ["status"])

    op.drop_index("ix_jira_stories_status_id", table_name="jira_stories")
    op.drop_constraint("fk_jira_stories_status_id", "jira_stories", type_="foreignkey")
    op.drop_column("jira_stories", "status_id")
    op.drop_table("story_statuses")
