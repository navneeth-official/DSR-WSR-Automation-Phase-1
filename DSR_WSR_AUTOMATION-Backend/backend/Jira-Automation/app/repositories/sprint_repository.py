from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sprint import Sprint
from app.services.sprint_date_merge import merge_sprint_end_date, merge_sprint_start_date


class SprintRepository:
    """Data access layer for sprints table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, sprint_id: int) -> Sprint | None:
        return self.db.get(Sprint, sprint_id)

    def get_by_project_and_name(self, project_id: int, sprint_name: str) -> Sprint | None:
        stmt = select(Sprint).where(
            Sprint.project_id == project_id,
            Sprint.sprint_name == sprint_name.strip(),
        )
        return self.db.scalars(stmt).first()

    def get_by_name(self, sprint_name: str) -> Sprint | None:
        """Legacy lookup by name only (first match). Prefer get_by_project_and_name."""
        stmt = select(Sprint).where(Sprint.sprint_name == sprint_name.strip())
        return self.db.scalars(stmt).first()

    def get_all(self) -> list[Sprint]:
        stmt = select(Sprint).order_by(Sprint.project_id, Sprint.sprint_name)
        return list(self.db.scalars(stmt).all())

    def get_current_for_project(
        self,
        project_id: int,
        *,
        as_of: date | None = None,
    ) -> Sprint | None:
        """Return the sprint active on ``as_of`` for ``project_id``, if any."""
        view_date = as_of or date.today()
        stmt = (
            select(Sprint)
            .where(
                Sprint.project_id == project_id,
                Sprint.sprint_start_date.is_not(None),
                Sprint.sprint_end_date.is_not(None),
                Sprint.sprint_start_date <= view_date,
                Sprint.sprint_end_date >= view_date,
            )
            .order_by(Sprint.sprint_end_date.desc())
        )
        return self.db.scalars(stmt).first()

    def get_or_create(
        self,
        *,
        project_id: int,
        sprint_name: str | None,
        sprint_start_date: date | None = None,
        sprint_end_date: date | None = None,
    ) -> Sprint | None:
        """Find sprint by project + name or insert a new row."""
        if not sprint_name or not sprint_name.strip():
            return None

        name = sprint_name.strip()
        sprint = self.get_by_project_and_name(project_id, name)

        if sprint is None:
            sprint = Sprint(
                project_id=project_id,
                sprint_name=name,
                sprint_status="inprogress",
                sprint_start_date=sprint_start_date,
                sprint_end_date=sprint_end_date,
            )
            self.db.add(sprint)
            self.db.flush()
        else:
            # Widen the stored sprint window only — Rovo snapshots may carry
            # WSR-clipped dates; never replace a longer canonical range.
            if sprint_start_date is not None:
                sprint.sprint_start_date = merge_sprint_start_date(
                    sprint.sprint_start_date, sprint_start_date
                )
            if sprint_end_date is not None:
                sprint.sprint_end_date = merge_sprint_end_date(
                    sprint.sprint_end_date, sprint_end_date
                )
            self.db.flush()

        return sprint
