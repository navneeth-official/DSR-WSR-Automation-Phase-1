from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.team import Team
from app.models.user import User


class UserRepository:
    """Data access for application users and team lookups used by auth."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_username(self, username: str) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.team))
            .where(User.username == username)
        )
        return self.db.scalars(stmt).first()

    def get_team_by_name(self, team_name: str) -> Team | None:
        stmt = select(Team).where(Team.team_name == team_name)
        return self.db.scalars(stmt).first()

    def list_teams(self) -> list[Team]:
        stmt = select(Team).order_by(Team.team_name)
        return list(self.db.scalars(stmt).all())

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        team_id: int,
        is_pmo: bool = False,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            team_id=team_id,
            is_pmo=is_pmo,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        # Reload with team relationship for response mapping.
        loaded = self.get_by_username(username)
        assert loaded is not None
        return loaded
