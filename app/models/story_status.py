from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.jira_story import JiraStory


class StoryStatus(Base):
    """Lookup table for Jira workflow status names (jira_stories.status_id)."""

    __tablename__ = "story_statuses"

    status_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    stories: Mapped[list["JiraStory"]] = relationship(back_populates="story_status")

    def __repr__(self) -> str:
        return f"<StoryStatus(status_id={self.status_id!r}, status_name={self.status_name!r})>"