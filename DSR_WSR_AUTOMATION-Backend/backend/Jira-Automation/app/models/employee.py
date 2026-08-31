from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.team import Team


class Employee(Base):
    """Person working under a team (account)."""

    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

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

    team: Mapped["Team"] = relationship(back_populates="employees")
    track_assignments: Mapped[list["EmployeeTrack"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Employee(id={self.employee_id}, name={self.employee_name!r})>"


class EmployeeTrack(Base):
    """Maps an employee to a track (project) with an active/inactive flag."""

    __tablename__ = "employee_tracks"
    __table_args__ = (
        UniqueConstraint("employee_id", "project_id", name="uq_employee_tracks_employee_project"),
    )

    employee_track_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

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

    employee: Mapped["Employee"] = relationship(back_populates="track_assignments")
    project: Mapped["Project"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<EmployeeTrack(id={self.employee_track_id}, "
            f"employee_id={self.employee_id}, project_id={self.project_id}, "
            f"active={self.is_active})>"
        )
