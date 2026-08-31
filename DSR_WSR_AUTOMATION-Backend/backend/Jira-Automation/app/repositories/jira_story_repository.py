from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.jira_story import JiraStory
from app.models.project import Project
from app.models.sprint import Sprint
from app.repositories.project_repository import ProjectRepository
from app.repositories.sprint_repository import SprintRepository
from app.services.title_generator import assign_title_if_missing, force_regenerate_title


_UNSET = object()


class JiraStoryRepository:
    """Data access layer for jira_stories table (composite key: jira_key + snapshot_date)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._projects = ProjectRepository(db)
        self._sprints = SprintRepository(db)

    def get_by_key_and_date(self, jira_key: str, snapshot_date: date) -> JiraStory | None:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(
                JiraStory.jira_key == jira_key,
                JiraStory.snapshot_date == snapshot_date,
            )
        )
        return self.db.scalars(stmt).first()

    def get_latest_by_key(self, jira_key: str) -> JiraStory | None:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(JiraStory.jira_key == jira_key)
            .order_by(JiraStory.snapshot_date.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def get_history_by_key(self, jira_key: str) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(JiraStory.jira_key == jira_key)
            .order_by(JiraStory.snapshot_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def story_exists(self, jira_key: str) -> bool:
        stmt = select(JiraStory.jira_key).where(JiraStory.jira_key == jira_key).limit(1)
        return self.db.scalar(stmt) is not None

    def get_all_latest(self) -> list[JiraStory]:
        return self._distinct_latest(select(JiraStory))

    def get_all_versions(self) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .order_by(JiraStory.jira_key, JiraStory.snapshot_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_all_for_snapshot_date(self, snapshot_date: date) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(JiraStory.snapshot_date == snapshot_date)
            .order_by(JiraStory.jira_key)
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_latest_by_project_id(self, project_id: int) -> list[JiraStory]:
        stmt = select(JiraStory).where(JiraStory.project_id == project_id)
        return self._distinct_latest(stmt, order_by_created_date=True)

    def get_dsr_stories_for_track(self, project_id: int, dsr_date: date) -> list[JiraStory]:
        """Latest snapshot per jira_key for a track, in sprints active on ``dsr_date``."""
        latest = self.get_latest_by_project_id(project_id)
        filtered = [s for s in latest if _sprint_contains_date(s, dsr_date)]
        return sorted(filtered, key=_dsr_display_sort_key)

    def get_all_by_project_id(self, project_id: int) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(JiraStory.project_id == project_id)
            .order_by(JiraStory.jira_key, JiraStory.snapshot_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_latest_by_project_key(self, project_key: str) -> list[JiraStory]:
        stmt = select(JiraStory).join(Project).where(Project.project_key == project_key)
        return self._distinct_latest(stmt, order_by_created_date=True)

    def get_latest_by_sprint_id(self, sprint_id: int) -> list[JiraStory]:
        stmt = select(JiraStory).where(JiraStory.sprint_id == sprint_id)
        return self._distinct_latest(stmt, order_by_jira_key=True)

    def get_all_by_sprint_id(self, sprint_id: int) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(JiraStory.sprint_id == sprint_id)
            .order_by(JiraStory.jira_key, JiraStory.snapshot_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_latest_by_assignee(self, assignee: str) -> list[JiraStory]:
        stmt = select(JiraStory).where(JiraStory.assignee == assignee)
        return self._distinct_latest(stmt, order_by_created_date=True)

    def get_all_by_assignee(self, assignee: str) -> list[JiraStory]:
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(JiraStory.assignee == assignee)
            .order_by(JiraStory.jira_key, JiraStory.snapshot_date.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_latest_snapshot_date(self) -> date | None:
        stmt = select(func.max(JiraStory.snapshot_date))
        return self.db.scalar(stmt)

    def get_by_snapshot_date(self, snapshot_date: date) -> list[JiraStory]:
        """Stories for a WSR snapshot week with project and sprint loaded."""
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(JiraStory.snapshot_date == snapshot_date)
            .order_by(
                JiraStory.project_id,
                JiraStory.sprint_id,
                JiraStory.jira_key,
            )
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_dsr_for_project(self, project_id: int, report_date: date) -> list[JiraStory]:
        """Stories for DSR on report_date (exact snapshot_date match)."""
        stmt = (
            select(JiraStory)
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(
                JiraStory.project_id == project_id,
                JiraStory.snapshot_date == report_date,
            )
            .order_by(JiraStory.created_date.desc(), JiraStory.jira_key)
        )
        return list(self.db.scalars(stmt).unique().all())

    def get_for_wsr_date_range(
        self, start_date: date, end_date: date
    ) -> list[JiraStory]:
        """
        Stories for a WSR week: sprints overlapping the report window, with the best
        available snapshot per jira_key.

        Snapshot selection (per jira_key):
        1. Prefer the latest snapshot on or before ``end_date`` (as-of report week).
        2. If none exist, use the earliest snapshot after ``end_date`` (imported later).
        """
        sprint_overlaps = and_(
            Sprint.sprint_start_date.is_not(None),
            Sprint.sprint_end_date.is_not(None),
            Sprint.sprint_start_date <= end_date,
            Sprint.sprint_end_date >= start_date,
        )

        as_of_rank = case((JiraStory.snapshot_date <= end_date, 0), else_=1)
        as_of_date = case(
            (JiraStory.snapshot_date <= end_date, JiraStory.snapshot_date),
            else_=None,
        )
        future_date = case(
            (JiraStory.snapshot_date > end_date, JiraStory.snapshot_date),
            else_=None,
        )

        ranked = (
            select(
                JiraStory.jira_key,
                JiraStory.snapshot_date,
                func.row_number()
                .over(
                    partition_by=JiraStory.jira_key,
                    order_by=(
                        as_of_rank.asc(),
                        as_of_date.desc().nullslast(),
                        future_date.asc().nullslast(),
                    ),
                )
                .label("row_num"),
            )
            .join(Sprint, JiraStory.sprint_id == Sprint.sprint_id)
            .where(sprint_overlaps)
            .subquery()
        )

        stmt = (
            select(JiraStory)
            .join(
                ranked,
                and_(
                    JiraStory.jira_key == ranked.c.jira_key,
                    JiraStory.snapshot_date == ranked.c.snapshot_date,
                ),
            )
            .options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .where(ranked.c.row_num == 1)
            .order_by(
                JiraStory.project_id,
                JiraStory.sprint_id,
                JiraStory.jira_key,
            )
        )
        return list(self.db.scalars(stmt).unique().all())

    def upsert(
        self,
        *,
        jira_key: str,
        project_name: str,
        summary: str,
        status: str,
        snapshot_date: date,
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
        title: str | None = None,
        completion: Decimal | float | int | None = None,
        comment: str | None | object = _UNSET,
    ) -> JiraStory:
        """Insert or update a story snapshot for (jira_key, snapshot_date)."""
        project = self._projects.get_or_create(
            project_key=project_key,
            project_name=project_name,
        )
        sprint = self._sprints.get_or_create(
            project_id=project.project_id,
            sprint_name=sprint_name,
            sprint_start_date=sprint_start_date,
            sprint_end_date=sprint_end_date,
        )

        story = self.get_by_key_and_date(jira_key, snapshot_date)

        if story is None:
            prior = self.get_latest_by_key(jira_key)
            resolved_title = title
            if resolved_title is None and prior is not None:
                if _summary_description_unchanged(
                    prior.summary,
                    prior.description,
                    summary,
                    description,
                ):
                    prior_title = (prior.title or "").strip()
                    if prior_title:
                        resolved_title = prior.title
            story = JiraStory(
                jira_key=jira_key,
                snapshot_date=snapshot_date,
                project_id=project.project_id,
                sprint_id=sprint.sprint_id if sprint else None,
                summary=summary,
                description=description,
                issue_type=issue_type,
                priority=priority,
                assignee=assignee,
                reporter=reporter,
                status=status,
                story_points=_to_decimal(story_points),
                created_date=created_date,
                updated_date=updated_date,
                resolved_date=resolved_date,
                title=resolved_title,
                completion=_to_decimal(completion),
                comment=None if comment is _UNSET else comment,
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
            story.status = status
            story.story_points = _to_decimal(story_points)
            story.created_date = created_date
            story.updated_date = updated_date
            story.resolved_date = resolved_date
            if summary_changed or description_changed:
                story.title = None
            elif title is not None:
                story.title = title
            story.completion = _to_decimal(completion)
            if comment is not _UNSET:
                story.comment = comment

        self.db.commit()
        self.db.refresh(story)
        return self.get_by_key_and_date(jira_key, snapshot_date) or story

    def persist_generated_title(self, story: JiraStory) -> JiraStory:
        """Generate and persist ``title`` when missing (LLM or fallback)."""
        if assign_title_if_missing(story):
            self.db.commit()
            self.db.refresh(story)
            reloaded = self.get_by_key_and_date(story.jira_key, story.snapshot_date)
            if reloaded is not None:
                return reloaded
        return story

    def regenerate_and_persist_title(self, story: JiraStory) -> JiraStory:
        """Force-regenerate ``title`` from summary/description and persist."""
        if force_regenerate_title(story):
            self.db.commit()
            self.db.refresh(story)
            reloaded = self.get_by_key_and_date(story.jira_key, story.snapshot_date)
            if reloaded is not None:
                return reloaded
        return story

    def delete_snapshot(self, jira_key: str, snapshot_date: date) -> bool:
        story = self.get_by_key_and_date(jira_key, snapshot_date)
        if story is None:
            return False
        self.db.delete(story)
        self.db.commit()
        return True

    def _distinct_latest(
        self,
        base_stmt,
        *,
        order_by_jira_key: bool = False,
        order_by_created_date: bool = False,
    ) -> list[JiraStory]:
        stmt = (
            base_stmt.options(joinedload(JiraStory.project), joinedload(JiraStory.sprint))
            .distinct(JiraStory.jira_key)
            .order_by(JiraStory.jira_key, JiraStory.snapshot_date.desc())
        )
        stories = list(self.db.scalars(stmt).unique().all())
        if order_by_jira_key:
            return sorted(stories, key=lambda story: story.jira_key)
        if order_by_created_date:
            return sorted(
                stories,
                key=lambda story: (story.created_date or date.min, story.jira_key),
                reverse=True,
            )
        return stories


def _to_decimal(value: Decimal | float | int | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _summary_description_unchanged(
    prior_summary: str | None,
    prior_description: str | None,
    new_summary: str | None,
    new_description: str | None,
) -> bool:
    return _normalize_text(prior_summary) == _normalize_text(new_summary) and _normalize_text(
        prior_description
    ) == _normalize_text(new_description)


def _is_done_status(status: str | None) -> bool:
    s = _normalize_text(status).lower()
    return s in ("done", "closed", "resolved", "complete", "completed")


def _sprint_contains_date(story: JiraStory, dsr_date: date) -> bool:
    sprint = story.sprint
    if sprint is None:
        return False
    start = sprint.sprint_start_date
    end = sprint.sprint_end_date
    if start is None or end is None:
        return False
    return start <= dsr_date <= end


def _dsr_display_sort_key(story: JiraStory) -> tuple[int, int, str]:
    """Incomplete stories first, then newest snapshot_date descending."""
    done_rank = 1 if _is_done_status(story.status) else 0
    snap_ord = story.snapshot_date.toordinal() if story.snapshot_date else 0
    return (done_rank, -snap_ord, story.jira_key)
