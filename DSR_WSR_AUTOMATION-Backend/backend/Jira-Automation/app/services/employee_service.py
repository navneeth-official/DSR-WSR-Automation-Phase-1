from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.constants.teams import KNOWN_TEAM_NAMES
from app.models.employee import Employee, EmployeeTrack
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeDetailResponse,
    EmployeeTrackAssignRequest,
    EmployeeTrackListResponse,
    EmployeeTrackResponse,
    EmployeeTrackUpdateRequest,
)


class EmployeeService:
    """Manage employees and their track assignments per team."""

    def __init__(self, db: Session) -> None:
        self._employees = EmployeeRepository(db)
        self._projects = ProjectRepository(db)

    def list_by_team(
        self,
        team_name: str,
        *,
        active_only: bool = False,
    ) -> EmployeeTrackListResponse:
        normalized = team_name.strip()
        if normalized not in KNOWN_TEAM_NAMES:
            raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

        team = self._employees.get_team_by_name(normalized)
        if team is None:
            raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found in database")

        employees = self._employees.list_employees_for_team(team.team_id, active_only=active_only)
        rows = _flatten_employee_tracks(employees, active_only=active_only)
        return EmployeeTrackListResponse(count=len(rows), employees=rows)

    def list_by_track(
        self,
        track_id: int,
        *,
        active_only: bool = False,
    ) -> EmployeeTrackListResponse:
        project = self._projects.get_by_id(track_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Track with id '{track_id}' not found")

        assignments = self._employees.list_employees_for_track(
            track_id,
            active_only=active_only,
        )
        rows = [_to_track_response(assignment) for assignment in assignments]
        return EmployeeTrackListResponse(count=len(rows), employees=rows)

    def get_employee(self, employee_id: int) -> EmployeeDetailResponse:
        employee = self._employees.get_employee_by_id(employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found")

        tracks = []
        for assignment in sorted(
            employee.track_assignments,
            key=lambda a: (a.project.project_name if a.project else "", a.project_id),
        ):
            assignment.employee = employee
            tracks.append(_to_track_response(assignment))
        return EmployeeDetailResponse(
            employee_id=employee.employee_id,
            employee_name=employee.employee_name,
            team_id=employee.team.team_id,
            team_name=employee.team.team_name,
            tracks=tracks,
        )

    def create_employee(self, body: EmployeeCreateRequest) -> EmployeeTrackResponse:
        normalized_team = body.team_name.strip()
        if normalized_team not in KNOWN_TEAM_NAMES:
            raise HTTPException(status_code=404, detail=f"Team '{body.team_name}' not found")

        team = self._employees.get_team_by_name(normalized_team)
        if team is None:
            raise HTTPException(
                status_code=404,
                detail=f"Team '{body.team_name}' not found in database",
            )

        project = self._projects.get_by_id(body.project_id)
        if project is None:
            raise HTTPException(
                status_code=404,
                detail=f"Track with project_id '{body.project_id}' not found",
            )

        employee_name = body.employee_name.strip()
        existing_employee = self._employees.get_employee_by_name_ci(team.team_id, employee_name)
        if existing_employee is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Assignee '{employee_name}' already exists for team "
                    f"'{normalized_team}' (case-insensitive match)"
                ),
            )

        employee = self._employees.create_employee(
            employee_name=employee_name,
            team_id=team.team_id,
        )
        assignment = self._employees.add_track_assignment(
            employee_id=employee.employee_id,
            project_id=body.project_id,
            is_active=body.is_active,
        )
        assignment.employee = employee
        assignment.project = project
        employee.team = team
        return _to_track_response(assignment)

    def add_track_to_employee(
        self,
        employee_id: int,
        body: EmployeeTrackAssignRequest,
    ) -> EmployeeTrackResponse:
        employee = self._employees.get_employee_by_id(employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found")

        project = self._projects.get_by_id(body.project_id)
        if project is None:
            raise HTTPException(
                status_code=404,
                detail=f"Track with project_id '{body.project_id}' not found",
            )

        existing = self._employees.get_track_assignment(employee_id, body.project_id)
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Employee '{employee_id}' is already assigned to "
                    f"track '{body.project_id}'"
                ),
            )

        assignment = self._employees.add_track_assignment(
            employee_id=employee_id,
            project_id=body.project_id,
            is_active=body.is_active,
        )
        assignment.employee = employee
        assignment.project = project
        return _to_track_response(assignment)

    def update_track_assignment(
        self,
        employee_id: int,
        track_id: int,
        body: EmployeeTrackUpdateRequest,
    ) -> EmployeeTrackResponse:
        assignment = self._employees.get_track_assignment(employee_id, track_id)
        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No track assignment found for employee '{employee_id}' "
                    f"and track '{track_id}'"
                ),
            )

        employee = self._employees.get_employee_by_id(employee_id)
        project = self._projects.get_by_id(track_id)
        if employee is None or project is None:
            raise HTTPException(status_code=404, detail="Employee or track not found")

        updated = self._employees.update_track_assignment(assignment, is_active=body.is_active)
        updated.employee = employee
        updated.project = project
        return _to_track_response(updated)

    def remove_track_assignment(self, employee_id: int, track_id: int) -> None:
        assignment = self._employees.get_track_assignment(employee_id, track_id)
        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No track assignment found for employee '{employee_id}' "
                    f"and track '{track_id}'"
                ),
            )
        self._employees.delete_track_assignment(assignment)


def _flatten_employee_tracks(
    employees: list[Employee],
    *,
    active_only: bool,
) -> list[EmployeeTrackResponse]:
    rows: list[EmployeeTrackResponse] = []
    for employee in employees:
        for assignment in employee.track_assignments:
            if active_only and not assignment.is_active:
                continue
            if active_only and assignment.project is not None and not assignment.project.is_active:
                continue
            assignment.employee = employee
            rows.append(_to_track_response(assignment))
    return rows


def _to_track_response(assignment: EmployeeTrack) -> EmployeeTrackResponse:
    employee = assignment.employee
    project = assignment.project
    team = employee.team
    return EmployeeTrackResponse(
        employee_id=employee.employee_id,
        employee_name=employee.employee_name,
        team_id=team.team_id,
        team_name=team.team_name,
        project_id=project.project_id,
        track_id=project.project_id,
        project_key=project.project_key,
        project_name=project.project_name,
        is_active=assignment.is_active,
    )
