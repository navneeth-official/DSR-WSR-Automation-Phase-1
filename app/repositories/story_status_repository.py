from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.story_status import StoryStatus


class StoryStatusRepository:
    """Data access layer for story_statuses lookup table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, status_id: int) -> StoryStatus | None:
        return self.db.get(StoryStatus, status_id)

    def get_by_name(self, status_name: str) -> StoryStatus | None:
        name = status_name.strip()
        if not name:
            return None
        stmt = select(StoryStatus).where(StoryStatus.status_name == name)
        return self.db.scalars(stmt).first()

    def get_or_create(self, *, status_name: str) -> StoryStatus:
        """Find status by exact name or insert a new row."""
        name = (status_name or "Unknown").strip() or "Unknown"
        row = self.get_by_name(name)
        if row is not None:
            return row
        row = StoryStatus(status_name=name)
        self.db.add(row)
        self.db.flush()
        return row