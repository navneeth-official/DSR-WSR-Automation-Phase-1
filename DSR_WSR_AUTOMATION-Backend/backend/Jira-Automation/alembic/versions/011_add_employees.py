"""Add employees and employee_tracks tables.

Revision ID: 011_add_employees
Revises: 010_composite_jira_story_pk
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_add_employees"
down_revision: Union[str, None] = "010_composite_jira_story_pk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("team_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_name", sa.String(length=100), nullable=False),
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
        sa.PrimaryKeyConstraint("team_id"),
        sa.UniqueConstraint("team_name"),
    )
    op.create_index("ix_teams_team_name", "teams", ["team_name"])

    op.create_table(
        "employees",
        sa.Column("employee_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_name", sa.String(length=200), nullable=False),
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
        sa.PrimaryKeyConstraint("employee_id"),
    )
    op.create_index("ix_employees_employee_name", "employees", ["employee_name"])
    op.create_index("ix_employees_team_id", "employees", ["team_id"])

    op.create_table(
        "employee_tracks",
        sa.Column("employee_track_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.employee_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("employee_track_id"),
        sa.UniqueConstraint(
            "employee_id",
            "project_id",
            name="uq_employee_tracks_employee_project",
        ),
    )
    op.create_index("ix_employee_tracks_employee_id", "employee_tracks", ["employee_id"])
    op.create_index("ix_employee_tracks_project_id", "employee_tracks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_employee_tracks_project_id", table_name="employee_tracks")
    op.drop_index("ix_employee_tracks_employee_id", table_name="employee_tracks")
    op.drop_table("employee_tracks")
    op.drop_index("ix_employees_team_id", table_name="employees")
    op.drop_index("ix_employees_employee_name", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_teams_team_name", table_name="teams")
    op.drop_table("teams")
