from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.jira_story import JiraStory
from app.models.project import Project
from app.models.sprint import Sprint
from app.repositories.project_repository import ProjectRepository
from app.repositories.sprint_repository import SprintRepository
from app.repositories.story_status_repository import StoryStatusRepository
from app.services.wsr_story_selection import select_wsr_story_snapshots


class JiraStoryRepository:
    """Data access layer for jira_stories table."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._projects = ProjectRepository(db)
        self._sprints = SprintRepository(db)
        self._statuses = StoryStatusRepository(db)

    @staticmethod
    def _story_load_options():
        return (
            joinedload(JiraStory.project),
            joinedload(JiraStory.sprint),
            joinedload(JiraStory.story_status),
        )

    def get_by_key(self, jira_key: str) -> JiraStory | None:
        stmt = (
            select(JiraStory)
            .options(*JiraStoryRepository._story_load_options())
            .where(JiraStory.jira_key == jira_key)
        )
        return self.db.scalars(stmt).first()

    def get_all(self) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(*JiraStoryRepository._story_load_options())
            .order_by(JiraStory.created_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_by_project_id(self, project_id: int) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(*JiraStoryRepository._story_load_options())
            .where(JiraStory.project_id == project_id)
            .order_by(JiraStory.created_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_by_project_key(self, project_key: str) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .join(Project)
            .options(*JiraStoryRepository._story_load_options())
            .where(Project.project_key == project_key)
            .order_by(JiraStory.created_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_by_sprint_id(self, sprint_id: int) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(*JiraStoryRepository._story_load_options())
            .where(JiraStory.sprint_id == sprint_id)
            .order_by(JiraStory.jira_key)
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_by_assignee(self, assignee: str) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(*JiraStoryRepository._story_load_options())
            .where(JiraStory.assignee == assignee)
            .order_by(JiraStory.created_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_latest_snapshot_date(self) -> date | None:
        """Return the most recent snapshot_date in jira_stories, if any."""
        stmt = select(func.max(JiraStory.snapshot_date))
        return self.db.scalar(stmt)

    def get_by_snapshot_date(self, snapshot_date: date) -> list[JiraStory]:
        """Stories for a WSR snapshot week with project and sprint loaded."""
        stmt = (
            select(JiraStory)
            .options(*JiraStoryRepository._story_load_options())
            .where(JiraStory.snapshot_date == snapshot_date)
            .order_by(
                JiraStory.project_id,
                JiraStory.sprint_id,
                JiraStory.jira_key,
            )
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_for_wsr_date_range(
        self, start_date: date, end_date: date
    ) -> list[JiraStory]:
        """
        Stories for WSR: all stories on sprints whose duration overlaps the
        report range (inclusive).

        Overlap: sprint_start_date <= end_date AND sprint_end_date >= start_date

        After sprint filtering, one snapshot row per ``jira_key`` is selected
        via ``select_wsr_story_snapshots`` (latest in-range snapshot, else latest
        overall).
        """
        sprint_eligible = and_(
            Sprint.sprint_start_date.is_not(None),
            Sprint.sprint_end_date.is_not(None),
            Sprint.sprint_start_date <= end_date,
            Sprint.sprint_end_date >= start_date,
        )
        stmt = (
            select(JiraStory)
            .join(Sprint, JiraStory.sprint_id == Sprint.sprint_id)
            .options(*JiraStoryRepository._story_load_options())
            .where(sprint_eligible)
            .order_by(
                JiraStory.project_id,
                JiraStory.sprint_id,
                JiraStory.jira_key,
            )
        )
        candidates = list(self.db.scalars(stmt).unique().all())
        return select_wsr_story_snapshots(candidates, start_date, end_date)

    def upsert(
        self,
        *,
        jira_key: str,
        project_name: str,
        summary: str,
        status: str,
        project_key: str | None = None,
        sprint_name: str | None = None,
        sprint_start_date: date | None = None,
        sprint_end_date: date | None = None,
        description: str | None = None,
        issue_type: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        reporter: str | None = None,
        story_points: Decimal | float | int | None = None,
        created_date: date | None = None,
        updated_date: date | None = None,
        resolved_date: date | None = None,
        snapshot_date: date | None = None,
        title: str | None = None,
        completion: Decimal | float | int | None = None,
    ) -> JiraStory:
        """Insert a new story or update an existing one by jira_key."""
        project = self._projects.get_or_create(
            project_key=project_key,
            project_name=project_name,
        )
        sprint = self._sprints.get_or_create(
            sprint_name=sprint_name,
            sprint_start_date=sprint_start_date,
            sprint_end_date=sprint_end_date,
        )
        status_row = self._statuses.get_or_create(status_name=status)

        story = self.db.get(JiraStory, jira_key)

        if story is None:
            story = JiraStory(
                jira_key=jira_key,
                project_id=project.project_id,
                sprint_id=sprint.sprint_id if sprint else None,
                status_id=status_row.status_id,
                summary=summary,
                description=description,
                issue_type=issue_type,
                priority=priority,
                assignee=assignee,
                reporter=reporter,
                story_points=_to_decimal(story_points),
                created_date=created_date,
                updated_date=updated_date,
                resolved_date=resolved_date,
                snapshot_date=snapshot_date,
                title=title,
                completion=_to_decimal(completion),
            )
            self.db.add(story)
        else:
            summary_changed = story.summary != summary
            description_changed = story.description != description
            story.project_id = project.project_id
            story.sprint_id = sprint.sprint_id if sprint else None
            story.summary = summary
            story.description = description
            story.issue_type = issue_type
            story.priority = priority
            story.assignee = assignee
            story.reporter = reporter
            story.status_id = status_row.status_id
            story.story_points = _to_decimal(story_points)
            story.created_date = created_date
            story.updated_date = updated_date
            story.resolved_date = resolved_date
            story.snapshot_date = snapshot_date
            # Clear title when source text changes so GPT regenerates on next PPT run.
            if summary_changed or description_changed:
                story.title = None
            elif title is not None:
                story.title = title
            story.completion = _to_decimal(completion)

        self.db.commit()
        self.db.refresh(story)
        return story

    def delete(self, jira_key: str) -> bool:
        story = self.db.get(JiraStory, jira_key)
        if story is None:
            return False
        self.db.delete(story)
        self.db.commit()
        return True


def _to_decimal(value: Decimal | float | int | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
