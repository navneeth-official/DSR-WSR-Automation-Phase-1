from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StoryStatus(Base):
    """Lookup of story statuses referenced by ``jira_stories.status_id``."""

    __tablename__ = "story_statuses"

    status_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    status_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<StoryStatus(status_id={self.status_id!r}, status_name={self.status_name!r})>"
