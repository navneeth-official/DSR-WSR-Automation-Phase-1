from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.track import (
    TrackCreateRequest,
    TrackListResponse,
    TrackResponse,
    TrackUpdateRequest,
)
from app.services.track_service import TrackService

router = APIRouter(prefix="/api/tracks", tags=["tracks"])


@router.get("", response_model=TrackListResponse)
def list_tracks(
    active_only: bool = Query(
        default=False,
        description="When true, return only active tracks",
    ),
    db: Session = Depends(get_db),
) -> TrackListResponse:
    """List all tracks in the projects table."""
    return TrackService(db).list_tracks(active_only=active_only)


@router.post("", response_model=TrackResponse, status_code=201)
def create_track(
    body: TrackCreateRequest,
    db: Session = Depends(get_db),
) -> TrackResponse:
    """Add a new track to the projects table."""
    return TrackService(db).create_track(body)


@router.patch("/{track_id}", response_model=TrackResponse)
def update_track(
    track_id: int,
    body: TrackUpdateRequest,
    db: Session = Depends(get_db),
) -> TrackResponse:
    """Update track metadata (currently active/inactive status)."""
    return TrackService(db).update_track(track_id, is_active=body.is_active)
