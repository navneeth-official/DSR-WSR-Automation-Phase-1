"""Add optional developer comment to jira_stories.

Revision ID: 014_add_jira_story_comment
Revises: 012_employee_assignments_view
Create Date: 2026-08-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "014_add_jira_story_comment"
down_revision: Union[str, None] = "013_add_project_is_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {col["name"] for col in inspect(bind).get_columns("jira_stories")}
    if "comment" in cols:
        return
    op.add_column(
        "jira_stories",
        sa.Column("comment", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jira_stories", "comment")
