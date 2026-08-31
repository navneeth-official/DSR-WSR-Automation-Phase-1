"""Add is_active flag to projects (tracks).

Revision ID: 013_add_project_is_active
Revises: 012_employee_assignments_view
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_add_project_is_active"
down_revision: Union[str, None] = "012_employee_assignments_view"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("projects", "is_active")
