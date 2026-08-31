from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.project import Project
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.project_repository import ProjectRepository, normalize_project_key
from app.schemas.track import TrackCreateRequest, TrackListResponse, TrackResponse


class TrackService:
    """Manage tracks (projects lookup table)."""

    def __init__(self, db: Session) -> None:
        self._projects = ProjectRepository(db)
        self._employees = EmployeeRepository(db)

    def list_tracks(self, *, active_only: bool = False) -> TrackListResponse:
        projects = (
            self._projects.get_all_active() if active_only else self._projects.get_all()
        )
        tracks = [_to_response(project) for project in projects]
        return TrackListResponse(count=len(tracks), tracks=tracks)

    def create_track(self, body: TrackCreateRequest) -> TrackResponse:
        project_key = normalize_project_key(body.project_key, body.project_name)
        project_name = body.project_name.strip()

        existing_by_name = self._projects.get_by_name_ci(project_name)
        if existing_by_name is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Track with name '{project_name}' already exists "
                    f"(case-insensitive match)"
                ),
            )

        existing_by_key = self._projects.get_by_key_ci(project_key)
        if existing_by_key is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Track with key '{project_key}' already exists "
                    f"(case-insensitive match)"
                ),
            )

        project = self._projects.create(
            project_key=project_key,
            project_name=project_name,
            is_active=body.is_active,
        )
        return _to_response(project)

    def update_track(self, track_id: int, *, is_active: bool) -> TrackResponse:
        project = self._projects.get_by_id(track_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Track with id '{track_id}' not found")

        self._projects.set_is_active(track_id, is_active)
        if not is_active:
            self._employees.deactivate_assignments_for_track(track_id)
        updated = self._projects.get_by_id(track_id)
        assert updated is not None
        return _to_response(updated)


def _to_response(project: Project) -> TrackResponse:
    return TrackResponse(
        project_id=project.project_id,
        track_id=project.project_id,
        project_key=project.project_key,
        project_name=project.project_name,
        is_active=project.is_active,
    )
