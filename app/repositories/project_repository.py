from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project


def normalize_project_key(project_key: str | None, project_name: str) -> str:
    """Use the Jira project key when present; otherwise the project name."""
    if project_key and project_key.strip():
        return project_key.strip()
    return project_name.strip()


class ProjectRepository:
    """Data access layer for projects table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)

    def get_by_key(self, project_key: str) -> Project | None:
        stmt = select(Project).where(Project.project_key == project_key)
        return self.db.scalars(stmt).first()

    def get_all(self) -> list[Project]:
        stmt = select(Project).order_by(Project.project_name)
        return list(self.db.scalars(stmt).all())

    def get_or_create(
        self,
        *,
        project_key: str | None,
        project_name: str,
    ) -> Project:
        """Find project by key or insert a new row with the next project_id."""
        key = normalize_project_key(project_key, project_name)
        project = self.get_by_key(key)

        if project is None:
            project = Project(project_key=key, project_name=project_name)
            self.db.add(project)
            self.db.flush()
        elif project.project_name != project_name:
            project.project_name = project_name
            self.db.flush()

        return project
