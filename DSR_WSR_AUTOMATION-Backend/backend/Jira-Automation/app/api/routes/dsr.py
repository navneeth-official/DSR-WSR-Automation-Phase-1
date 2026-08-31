from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dsr import TeamTracksResponse, TrackDsrResponse
from app.services.dsr_service import DsrService

router = APIRouter(prefix="/api", tags=["dsr"])


@router.get("/teams/{team_name}/tracks", response_model=TeamTracksResponse)
def list_team_tracks(team_name: str, db: Session = Depends(get_db)) -> TeamTracksResponse:
    """List all tracks (projects) under a team for the sidebar."""
    return DsrService(db).list_tracks_for_team(team_name)


@router.get("/dsr/tracks/{project_key}", response_model=TrackDsrResponse)
def get_track_dsr(
    project_key: str,
    report_date: date | None = Query(
        default=None,
        description="DSR date (defaults to today). Matches snapshot_date exactly.",
    ),
    db: Session = Depends(get_db),
) -> TrackDsrResponse:
    """Daily Status Report for a track on report_date (default: today)."""
    return DsrService(db).get_track_dsr(project_key, report_date=report_date)
