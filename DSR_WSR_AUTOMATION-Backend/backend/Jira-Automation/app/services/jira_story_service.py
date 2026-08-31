from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.constants.projects import CANONICAL_PROJECT_KEYS
from app.models.jira_story import JiraStory
from app.repositories.jira_story_repository import JiraStoryRepository
from app.repositories.project_repository import ProjectRepository, normalize_project_key
from app.schemas.jira_story import (
    JiraStoryCreateRequest,
    JiraStoryListResponse,
    JiraStoryResponse,
    JiraStorySaveRequest,
    TitleSuggestionsResponse,
)
from app.services.title_generator import suggest_regenerated_titles
from app.services.rovo_import import infer_completion


class JiraStoryService:
    """Read, create, and update Jira story snapshots from the frontend."""

    def __init__(self, db: Session) -> None:
        self._stories = JiraStoryRepository(db)
        self._projects = ProjectRepository(db)

    def list_stories(
        self,
        *,
        snapshot_date: date | None = None,
        all_versions: bool = False,
    ) -> JiraStoryListResponse:
        if snapshot_date is not None:
            stories = self._stories.get_all_for_snapshot_date(snapshot_date)
        elif all_versions:
            stories = self._stories.get_all_versions()
        else:
            stories = self._stories.get_all_latest()
        return _to_list_response(stories)

    def list_story_history(self, jira_key: str) -> JiraStoryListResponse:
        stories = self._stories.get_history_by_key(jira_key)
        if not stories:
            raise HTTPException(status_code=404, detail=f"Story '{jira_key}' not found")
        return _to_list_response(stories)

    def list_stories_by_track_id(
        self, track_id: int, *, all_versions: bool = False
    ) -> JiraStoryListResponse:
        project = self._projects.get_by_id(track_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Track with id '{track_id}' not found")

        if all_versions:
            stories = self._stories.get_all_by_project_id(track_id)
        else:
            stories = self._stories.get_latest_by_project_id(track_id)
        return _to_list_response(stories)

    def list_dsr_stories_for_track(
        self,
        track_id: int,
        dsr_date: date,
    ) -> JiraStoryListResponse:
        """Stories for View DSR: latest per key in sprints active on ``dsr_date``."""
        project = self._projects.get_by_id(track_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Track with id '{track_id}' not found")

        stories = self._stories.get_dsr_stories_for_track(track_id, dsr_date)
        return _to_list_response(stories)

    def list_stories_by_assignee(
        self, assignee: str, *, all_versions: bool = False
    ) -> JiraStoryListResponse:
        if all_versions:
            stories = self._stories.get_all_by_assignee(assignee)
        else:
            stories = self._stories.get_latest_by_assignee(assignee)
        return _to_list_response(stories)

    def list_stories_by_sprint_id(
        self, sprint_id: int, *, all_versions: bool = False
    ) -> JiraStoryListResponse:
        if all_versions:
            stories = self._stories.get_all_by_sprint_id(sprint_id)
        else:
            stories = self._stories.get_latest_by_sprint_id(sprint_id)
        return _to_list_response(stories)

    def create_story(self, body: JiraStorySaveRequest) -> JiraStoryResponse:
        snapshot_date = body.snapshot_date or date.today()
        if self._stories.get_by_key_and_date(body.jira_key, snapshot_date) is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Story '{body.jira_key}' already has a snapshot for "
                    f"{snapshot_date.isoformat()}"
                ),
            )

        story = self._save_story(body, snapshot_date=snapshot_date)
        reloaded = self._stories.get_by_key_and_date(story.jira_key, story.snapshot_date)
        return _to_response(reloaded or story)

    def update_story_from_body(self, body: JiraStorySaveRequest) -> JiraStoryResponse:
        snapshot_date = body.snapshot_date or date.today()
        if not self._stories.story_exists(body.jira_key):
            raise HTTPException(status_code=404, detail=f"Story '{body.jira_key}' not found")

        story = self._save_story(body, snapshot_date=snapshot_date)
        reloaded = self._stories.get_by_key_and_date(story.jira_key, story.snapshot_date)
        return _to_response(reloaded or story)

    def update_story(self, jira_key: str, body: JiraStorySaveRequest) -> JiraStoryResponse:
        if body.jira_key != jira_key:
            raise HTTPException(
                status_code=400,
                detail="jira_key in URL must match jira_key in request body",
            )
        return self.update_story_from_body(body)

    def add_story_comment(self, jira_key: str, comment: str) -> JiraStoryResponse:
        """Append a developer comment as a new snapshot version (never overwrites prior rows)."""
        text = comment.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Comment cannot be empty")

        latest = self._stories.get_latest_by_key(jira_key)
        if latest is None:
            raise HTTPException(status_code=404, detail=f"Story '{jira_key}' not found")

        snapshot_date = self._next_snapshot_date(jira_key)
        body = _story_to_save_request(latest)
        body = body.model_copy(
            update={
                "comment": text,
                "snapshot_date": snapshot_date,
                "updated_date": date.today(),
            }
        )
        story = self._save_story(body, snapshot_date=snapshot_date)
        reloaded = self._stories.get_by_key_and_date(story.jira_key, story.snapshot_date)
        return _to_response(reloaded or story)

    def suggest_story_titles(
        self,
        jira_key: str,
        *,
        snapshot_date: date | None = None,
    ) -> TitleSuggestionsResponse:
        snap = snapshot_date or date.today()
        story = self._stories.get_by_key_and_date(jira_key, snap)
        if story is None:
            story = self._stories.get_latest_by_key(jira_key)
        if story is None:
            raise HTTPException(status_code=404, detail=f"Story '{jira_key}' not found")

        suggestions = suggest_regenerated_titles(story)
        return TitleSuggestionsResponse(
            jira_key=story.jira_key,
            snapshot_date=story.snapshot_date,
            title=story.title,
            suggestions=suggestions,
        )

    def _save_story(self, body: JiraStorySaveRequest, *, snapshot_date: date) -> JiraStory:
        project_key, project_name = _resolve_track(body.track)
        completion = body.percent_complete
        if completion is None:
            completion = infer_completion(body.status)

        today = date.today()
        existing = self._stories.get_by_key_and_date(body.jira_key, snapshot_date)
        if existing is None:
            prior = self._stories.get_latest_by_key(body.jira_key)
        else:
            prior = existing

        created_date = body.date_assigned
        if created_date is None:
            created_date = prior.created_date if prior else today

        updated_date = body.updated_date or today

        upsert_kwargs: dict = {
            "jira_key": body.jira_key,
            "snapshot_date": snapshot_date,
            "project_key": project_key,
            "project_name": project_name,
            "sprint_name": body.sprint,
            "sprint_start_date": body.sprint_start_date,
            "sprint_end_date": body.sprint_end_date,
            "title": body.title,
            "summary": body.summary,
            "description": body.description,
            "issue_type": body.issue_type,
            "priority": body.priority,
            "assignee": body.assignee,
            "reporter": body.reportee,
            "status": body.status,
            "story_points": body.story_points,
            "created_date": created_date,
            "updated_date": updated_date,
            "resolved_date": body.resolved_date,
            "completion": completion,
        }
        if "comment" in body.model_fields_set:
            upsert_kwargs["comment"] = body.comment

        story = self._stories.upsert(**upsert_kwargs)
        return self._stories.persist_generated_title(story)

    def _next_snapshot_date(self, jira_key: str) -> date:
        """Pick the next unused snapshot date for a new version row."""
        today = date.today()
        latest = self._stories.get_latest_by_key(jira_key)
        candidate = today
        if latest is not None:
            candidate = max(today, latest.snapshot_date)
        while self._stories.get_by_key_and_date(jira_key, candidate) is not None:
            candidate += timedelta(days=1)
        return candidate


def _story_to_save_request(story: JiraStory) -> JiraStorySaveRequest:
    sprint = story.sprint
    return JiraStorySaveRequest(
        jira_key=story.jira_key,
        summary=story.summary,
        track=story.project.project_key,
        sprint=sprint.sprint_name if sprint else None,
        sprint_start_date=sprint.sprint_start_date if sprint else None,
        sprint_end_date=sprint.sprint_end_date if sprint else None,
        date_assigned=story.created_date,
        status=story.status,
        story_points=story.story_points,
        percent_complete=story.completion,
        assignee=story.assignee,
        reportee=story.reporter,
        title=story.title,
        description=story.description,
        issue_type=story.issue_type,
        priority=story.priority,
        updated_date=story.updated_date,
        resolved_date=story.resolved_date,
        snapshot_date=story.snapshot_date,
    )


def _resolve_track(track: str) -> tuple[str, str]:
    normalized = track.strip()
    project_key = normalize_project_key(normalized, normalized)

    for name, key in CANONICAL_PROJECT_KEYS.items():
        if key == project_key:
            return key, name

    if normalized in CANONICAL_PROJECT_KEYS:
        return CANONICAL_PROJECT_KEYS[normalized], normalized

    return project_key, normalized


def _to_list_response(stories: list[JiraStory]) -> JiraStoryListResponse:
    return JiraStoryListResponse(
        count=len(stories),
        stories=[_to_response(story) for story in stories],
    )


def _to_response(story: JiraStory) -> JiraStoryResponse:
    return JiraStoryResponse(
        jira_key=story.jira_key,
        project_id=story.project_id,
        project_key=story.project.project_key,
        project_name=story.project.project_name,
        sprint_id=story.sprint_id,
        sprint_name=story.sprint.sprint_name if story.sprint else None,
        sprint_start_date=story.sprint.sprint_start_date if story.sprint else None,
        sprint_end_date=story.sprint.sprint_end_date if story.sprint else None,
        title=story.title,
        summary=story.summary,
        description=story.description,
        issue_type=story.issue_type,
        priority=story.priority,
        assignee=story.assignee,
        reportee=story.reporter,
        comment=story.comment,
        status=story.status,
        story_points=story.story_points,
        percent_complete=story.completion,
        date_assigned=story.created_date,
        updated_date=story.updated_date,
        resolved_date=story.resolved_date,
        snapshot_date=story.snapshot_date,
    )
