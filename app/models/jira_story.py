from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.sprint import Sprint
    from app.models.story_status import StoryStatus


class JiraStory(Base):
    """Stores Jira story details synced from Rovo AI for DSR/WSR report generation."""

    __tablename__ = "jira_stories"

    jira_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sprint_id: Mapped[int | None] = mapped_column(
        ForeignKey("sprints.sprint_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status_id: Mapped[int] = mapped_column(
        ForeignKey("story_statuses.status_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="AI-generated title from summary and description (filled later)",
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_points: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    assignee: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    reporter: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issue_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completion: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Story completion percentage (0-100)",
    )
    created_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(back_populates="stories")
    sprint: Mapped["Sprint | None"] = relationship(back_populates="stories")
    story_status: Mapped["StoryStatus"] = relationship(back_populates="stories")

    @property
    def status(self) -> str:
        """Jira workflow status label (from story_statuses.status_name)."""
        if self.story_status is not None:
            return self.story_status.status_name
        return ""

    def __repr__(self) -> str:
        return f"<JiraStory(jira_key={self.jira_key!r}, status={self.status!r})>"