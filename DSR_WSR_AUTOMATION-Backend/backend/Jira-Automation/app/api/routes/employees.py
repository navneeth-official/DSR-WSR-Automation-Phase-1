from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeDetailResponse,
    EmployeeTrackAssignRequest,
    EmployeeTrackListResponse,
    EmployeeTrackResponse,
    EmployeeTrackUpdateRequest,
)
from app.services.employee_service import EmployeeService

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("/team/{team_name}", response_model=EmployeeTrackListResponse)
def list_employees_by_team(
    team_name: str,
    active_only: bool = Query(
        default=False,
        description="When true, return only active track assignments",
    ),
    db: Session = Depends(get_db),
) -> EmployeeTrackListResponse:
    """List employees and their track assignments for a team (account)."""
    return EmployeeService(db).list_by_team(team_name, active_only=active_only)


@router.get("/track/{track_id}", response_model=EmployeeTrackListResponse)
def list_employees_by_track(
    track_id: int,
    active_only: bool = Query(
        default=False,
        description="When true, return only active track assignments",
    ),
    db: Session = Depends(get_db),
) -> EmployeeTrackListResponse:
    """List employees assigned to a track (project_id)."""
    return EmployeeService(db).list_by_track(track_id, active_only=active_only)


@router.get("/{employee_id}", response_model=EmployeeDetailResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
) -> EmployeeDetailResponse:
    """Get one employee and all track assignments."""
    return EmployeeService(db).get_employee(employee_id)


@router.post("", response_model=EmployeeTrackResponse, status_code=201)
def create_employee(
    body: EmployeeCreateRequest,
    db: Session = Depends(get_db),
) -> EmployeeTrackResponse:
    """Create an employee under a team and assign their first track."""
    return EmployeeService(db).create_employee(body)


@router.post("/{employee_id}/tracks", response_model=EmployeeTrackResponse, status_code=201)
def assign_track_to_employee(
    employee_id: int,
    body: EmployeeTrackAssignRequest,
    db: Session = Depends(get_db),
) -> EmployeeTrackResponse:
    """Add another track assignment for an existing employee."""
    return EmployeeService(db).add_track_to_employee(employee_id, body)


@router.patch("/{employee_id}/tracks/{track_id}", response_model=EmployeeTrackResponse)
def update_employee_track(
    employee_id: int,
    track_id: int,
    body: EmployeeTrackUpdateRequest,
    db: Session = Depends(get_db),
) -> EmployeeTrackResponse:
    """Activate or deactivate a track assignment (e.g. mark locations as inactive)."""
    return EmployeeService(db).update_track_assignment(employee_id, track_id, body)


@router.delete("/{employee_id}/tracks/{track_id}", status_code=204)
def remove_employee_track(
    employee_id: int,
    track_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Remove a track assignment for an employee."""
    EmployeeService(db).remove_track_assignment(employee_id, track_id)
