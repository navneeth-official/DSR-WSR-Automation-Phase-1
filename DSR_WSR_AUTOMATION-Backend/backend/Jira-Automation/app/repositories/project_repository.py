from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants.projects import CANONICAL_PROJECT_KEYS
from app.models.project import Project


def normalize_project_key(project_key: str | None, project_name: str) -> str:
    """Return a stable string key used to look up or create a project row."""
    name = project_name.strip()
    if name in CANONICAL_PROJECT_KEYS:
        return CANONICAL_PROJECT_KEYS[name]
    if project_key and project_key.strip():
        return project_key.strip()
    return name


class ProjectRepository:
    """Data access layer for projects table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, project_id: int) -> Project | None:
        return self.db.get(Project, project_id)

    def get_by_key(self, project_key: str) -> Project | None:
        stmt = select(Project).where(Project.project_key == project_key)
        return self.db.scalars(stmt).first()

    def get_by_key_ci(self, project_key: str) -> Project | None:
        normalized = project_key.strip()
        if not normalized:
            return None
        stmt = select(Project).where(func.lower(Project.project_key) == normalized.lower())
        return self.db.scalars(stmt).first()

    def get_by_name_ci(self, project_name: str) -> Project | None:
        normalized = project_name.strip()
        if not normalized:
            return None
        stmt = select(Project).where(func.lower(Project.project_name) == normalized.lower())
        return self.db.scalars(stmt).first()

    def get_all(self) -> list[Project]:
        stmt = select(Project).order_by(Project.project_name)
        return list(self.db.scalars(stmt).all())

    def get_all_active(self) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.is_active.is_(True))
            .order_by(Project.project_name)
        )
        return list(self.db.scalars(stmt).all())

    def set_is_active(self, project_id: int, is_active: bool) -> None:
        project = self.get_by_id(project_id)
        if project is not None:
            project.is_active = is_active
            self.db.commit()

    def create(
        self,
        *,
        project_key: str,
        project_name: str,
        is_active: bool = True,
    ) -> Project:
        project = Project(
            project_key=project_key,
            project_name=project_name,
            is_active=is_active,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

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
