from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.jira_story import (
    JiraStoryCreateRequest,
    JiraStoryListResponse,
    JiraStoryResponse,
    JiraStorySaveRequest,
    StoryCommentRequest,
    TitleSuggestionsResponse,
)
from app.services.jira_story_service import JiraStoryService

router = APIRouter(prefix="/api/stories", tags=["stories"])


@router.get("", response_model=JiraStoryListResponse)
def list_stories(
    snapshot_date: date | None = Query(
        default=None,
        description="Return all stories for this snapshot date. Omit for latest per jira_key.",
    ),
    all_versions: bool = Query(
        default=False,
        description="Return every snapshot row (Story Board). Default is latest per jira_key.",
    ),
    db: Session = Depends(get_db),
) -> JiraStoryListResponse:
    """List Jira stories (latest snapshot per key, all versions, or rows for a given date)."""
    return JiraStoryService(db).list_stories(
        snapshot_date=snapshot_date,
        all_versions=all_versions,
    )


@router.post("", response_model=JiraStoryResponse, status_code=201)
def create_story(
    body: JiraStoryCreateRequest,
    db: Session = Depends(get_db),
) -> JiraStoryResponse:
    """Create a new Jira story snapshot."""
    return JiraStoryService(db).create_story(body)


@router.put("", response_model=JiraStoryResponse)
def update_story(
    body: JiraStorySaveRequest,
    db: Session = Depends(get_db),
) -> JiraStoryResponse:
    """Upsert today's snapshot (or body snapshot_date) for an existing jira_key."""
    return JiraStoryService(db).update_story_from_body(body)


@router.post("/{jira_key}/regenerate-title", response_model=TitleSuggestionsResponse)
def regenerate_story_title(
    jira_key: str,
    snapshot_date: date | None = Query(
        default=None,
        description="Snapshot date for the row to regenerate (defaults to today).",
    ),
    db: Session = Depends(get_db),
) -> TitleSuggestionsResponse:
    """Return multiple AI title suggestions from the story summary and description."""
    return JiraStoryService(db).suggest_story_titles(
        jira_key,
        snapshot_date=snapshot_date,
    )


@router.get("/{jira_key}/history", response_model=JiraStoryListResponse)
def list_story_history(
    jira_key: str,
    db: Session = Depends(get_db),
) -> JiraStoryListResponse:
    """List all historical snapshots for one jira_key, newest first."""
    return JiraStoryService(db).list_story_history(jira_key)


@router.post("/{jira_key}/comment", response_model=JiraStoryResponse, status_code=201)
def add_story_comment(
    jira_key: str,
    body: StoryCommentRequest,
    db: Session = Depends(get_db),
) -> JiraStoryResponse:
    """Add a developer comment as a new snapshot version for the story."""
    return JiraStoryService(db).add_story_comment(jira_key, body.comment)


@router.get("/track/{track_id}/dsr", response_model=JiraStoryListResponse)
def list_dsr_stories_by_track(
    track_id: int,
    dsr_date: date | None = Query(
        default=None,
        description="DSR viewing date; returns latest stories in sprints active on this date.",
    ),
    db: Session = Depends(get_db),
) -> JiraStoryListResponse:
    """View DSR: latest snapshot per jira_key for sprints containing ``dsr_date``."""
    view_date = dsr_date or date.today()
    return JiraStoryService(db).list_dsr_stories_for_track(track_id, view_date)


@router.get("/track/{track_id}", response_model=JiraStoryListResponse)
def list_stories_by_track_id(
    track_id: int,
    all_versions: bool = Query(
        default=False,
        description="Return every snapshot for the track instead of latest per jira_key.",
    ),
    db: Session = Depends(get_db),
) -> JiraStoryListResponse:
    """List snapshots for a track (project_id)."""
    return JiraStoryService(db).list_stories_by_track_id(
        track_id, all_versions=all_versions
    )


@router.get("/assignee/{assignee}", response_model=JiraStoryListResponse)
def list_stories_by_assignee(
    assignee: str,
    all_versions: bool = Query(
        default=False,
        description="Return every matching snapshot instead of latest per jira_key.",
    ),
    db: Session = Depends(get_db),
) -> JiraStoryListResponse:
    """List snapshots assigned to a person."""
    return JiraStoryService(db).list_stories_by_assignee(
        assignee, all_versions=all_versions
    )


@router.get("/sprint/{sprint_id}", response_model=JiraStoryListResponse)
def list_stories_by_sprint_id(
    sprint_id: int,
    all_versions: bool = Query(
        default=False,
        description="Return every matching snapshot instead of latest per jira_key.",
    ),
    db: Session = Depends(get_db),
) -> JiraStoryListResponse:
    """List snapshots in a sprint."""
    return JiraStoryService(db).list_stories_by_sprint_id(
        sprint_id, all_versions=all_versions
    )


@router.put("/{jira_key}", response_model=JiraStoryResponse)
def update_story_by_key(
    jira_key: str,
    body: JiraStorySaveRequest,
    db: Session = Depends(get_db),
) -> JiraStoryResponse:
    """Upsert a snapshot. URL jira_key must match body jira_key."""
    return JiraStoryService(db).update_story(jira_key, body)
