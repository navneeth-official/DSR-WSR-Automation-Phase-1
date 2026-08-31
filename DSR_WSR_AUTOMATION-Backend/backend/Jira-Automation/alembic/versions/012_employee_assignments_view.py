"""Add employee_assignments view for easy browsing in pgAdmin.

Revision ID: 012_employee_assignments_view
Revises: 011_add_employees
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "012_employee_assignments_view"
down_revision: Union[str, None] = "011_add_employees"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VIEW_SQL = """
CREATE OR REPLACE VIEW employee_assignments AS
SELECT
    e.employee_id,
    e.employee_name,
    e.team_id,
    t.team_name,
    et.project_id,
    et.project_id AS track_id,
    p.project_key,
    p.project_name,
    et.is_active,
    et.employee_track_id,
    et.created_at,
    et.updated_at
FROM employees e
JOIN teams t ON t.team_id = e.team_id
JOIN employee_tracks et ON et.employee_id = e.employee_id
JOIN projects p ON p.project_id = et.project_id
"""


def upgrade() -> None:
    op.execute(VIEW_SQL)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS employee_assignments")
