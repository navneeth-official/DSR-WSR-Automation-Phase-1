from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.constants.teams import KNOWN_TEAM_NAMES
from app.models.jira_story import JiraStory
from app.repositories.jira_story_repository import JiraStoryRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.sprint_repository import SprintRepository
from app.schemas.dsr import (
    DsrStatusSummary,
    DsrStoryRow,
    SprintSummary,
    TeamTracksResponse,
    TrackDsrResponse,
    TrackListItem,
    TrackSummary,
)


class DsrService:
    """Build Daily Status Report payloads for the frontend."""

    def __init__(self, db: Session) -> None:
        self._projects = ProjectRepository(db)
        self._sprints = SprintRepository(db)
        self._stories = JiraStoryRepository(db)

    def list_tracks_for_team(self, team_name: str) -> TeamTracksResponse:
        normalized = team_name.strip()
        if normalized not in KNOWN_TEAM_NAMES:
            raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

        projects = self._projects.get_all()
        return TeamTracksResponse(
            team_name=normalized,
            tracks=[
                TrackListItem(
                    project_id=project.project_id,
                    project_key=project.project_key,
                    project_name=project.project_name,
                    is_active=project.is_active,
                )
                for project in projects
            ],
        )

    def get_track_dsr(
        self,
        project_key: str,
        team_name: str = "HEB",
        report_date: date | None = None,
    ) -> TrackDsrResponse:
        project = self._projects.get_by_key(project_key)
        if project is None:
            raise HTTPException(
                status_code=404,
                detail=f"Track with project_key '{project_key}' not found",
            )

        effective_date = report_date or date.today()
        stories = self._stories.get_dsr_for_project(project.project_id, effective_date)
        sprint = self._sprints.get_current_for_project(project.project_id)

        return TrackDsrResponse(
            track=TrackSummary(
                project_id=project.project_id,
                project_key=project.project_key,
                project_name=project.project_name,
                team_name=team_name,
            ),
            sprint=_to_sprint_summary(sprint),
            report_date=effective_date,
            summary=_build_summary(stories),
            stories=[_to_story_row(story) for story in stories],
        )


def _to_sprint_summary(sprint) -> SprintSummary | None:
    if sprint is None:
        return None
    return SprintSummary(
        sprint_id=sprint.sprint_id,
        sprint_name=sprint.sprint_name,
        sprint_start_date=sprint.sprint_start_date,
        sprint_end_date=sprint.sprint_end_date,
        sprint_status=sprint.sprint_status,
    )


def _to_story_row(story: JiraStory) -> DsrStoryRow:
    return DsrStoryRow(
        jira_key=story.jira_key,
        title=story.title or story.summary,
        date_assigned=story.created_date,
        status=story.status,
        story_points=story.story_points,
        percent_complete=story.completion,
        assignee=story.assignee,
        reportee=story.reporter,
        comment=story.comment,
    )


def _build_summary(stories: list[JiraStory]) -> DsrStatusSummary:
    todo = 0
    in_progress = 0
    done = 0
    completion_total = Decimal("0")
    completion_count = 0

    for story in stories:
        normalized = story.status.strip().lower()
        if normalized in {"done", "closed", "resolved"}:
            done += 1
        elif normalized in {"in progress", "in review", "in development"}:
            in_progress += 1
        elif normalized == "to do":
            todo += 1

        if story.completion is not None:
            completion_total += story.completion
            completion_count += 1

    completion_percent = 0
    if completion_count:
        completion_percent = int(round(completion_total / completion_count))

    return DsrStatusSummary(
        total=len(stories),
        todo=todo,
        in_progress=in_progress,
        done=done,
        completion_percent=completion_percent,
    )
