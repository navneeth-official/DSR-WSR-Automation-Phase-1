"""
Seed sample HEB employees and their track assignments.

Usage:
    python scripts/seed_employees.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models.employee  # noqa: F401
import app.models.jira_story  # noqa: F401
import app.models.project  # noqa: F401
import app.models.sprint  # noqa: F401
import app.models.team  # noqa: F401

from app.database import SessionLocal
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.project_repository import ProjectRepository

TEAM_NAME = "HEB"

EMPLOYEE_TRACKS: list[tuple[str, str, bool]] = [
    ("Rishi", "COST", True),
    ("Noble", "SUP", True),
    ("Noble", "LOC", False),
    ("Vineed", "SUP", True),
]


def seed_employees() -> None:
    db = SessionLocal()
    employees_repo = EmployeeRepository(db)
    projects_repo = ProjectRepository(db)

    team = employees_repo.get_team_by_name(TEAM_NAME)
    if team is None:
        raise RuntimeError(f"Team '{TEAM_NAME}' not found. Run alembic upgrade head first.")

    created_employees = 0
    created_assignments = 0
    updated_assignments = 0

    employee_ids: dict[str, int] = {}

    for employee_name, project_key, is_active in EMPLOYEE_TRACKS:
        if employee_name not in employee_ids:
            existing = _find_employee(employees_repo, team.team_id, employee_name)
            if existing is None:
                employee = employees_repo.create_employee(
                    employee_name=employee_name,
                    team_id=team.team_id,
                )
                created_employees += 1
            else:
                employee = existing
            employee_ids[employee_name] = employee.employee_id

        project = projects_repo.get_by_key(project_key)
        if project is None:
            raise RuntimeError(
                f"Project '{project_key}' not found. Run sql/reference_data.sql first."
            )

        employee_id = employee_ids[employee_name]
        assignment = employees_repo.get_track_assignment(employee_id, project.project_id)
        if assignment is None:
            employees_repo.add_track_assignment(
                employee_id=employee_id,
                project_id=project.project_id,
                is_active=is_active,
            )
            created_assignments += 1
        elif assignment.is_active != is_active:
            employees_repo.update_track_assignment(assignment, is_active=is_active)
            updated_assignments += 1

    print(
        f"Employee seed complete: "
        f"{created_employees} employees created, "
        f"{created_assignments} track assignments created, "
        f"{updated_assignments} assignments updated."
    )


def _find_employee(
    repo: EmployeeRepository,
    team_id: int,
    employee_name: str,
):
    for employee in repo.list_employees_for_team(team_id):
        if employee.employee_name == employee_name:
            return employee
    return None


if __name__ == "__main__":
    seed_employees()
