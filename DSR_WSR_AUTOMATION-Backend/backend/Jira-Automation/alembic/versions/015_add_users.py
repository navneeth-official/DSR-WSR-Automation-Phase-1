"""Add users table for signup/signin with team mapping.

Revision ID: 015_add_users
Revises: 014_add_jira_story_comment
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_add_users"
down_revision: Union[str, None] = "014_add_jira_story_comment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_team_id", "users", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_users_team_id", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
