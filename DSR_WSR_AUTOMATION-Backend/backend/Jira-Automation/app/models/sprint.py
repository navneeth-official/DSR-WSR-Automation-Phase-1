from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.jira_story import JiraStory
    from app.models.project import Project


class Sprint(Base):
    """Jira sprint lookup; one row per (project, sprint name)."""

    __tablename__ = "sprints"
    __table_args__ = (
        UniqueConstraint("project_id", "sprint_name", name="uq_sprints_project_name"),
    )

    sprint_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sprint_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    sprint_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="inprogress",
        index=True,
    )
    sprint_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sprint_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

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

    project: Mapped["Project"] = relationship(back_populates="sprints")
    stories: Mapped[list["JiraStory"]] = relationship(back_populates="sprint")

    def __repr__(self) -> str:
        return f"<Sprint(id={self.sprint_id}, name={self.sprint_name!r})>"
