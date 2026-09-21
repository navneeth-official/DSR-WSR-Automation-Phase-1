from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.repositories.employee_repository import EmployeeRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    SignupRequest,
    TeamListResponse,
    TeamOptionResponse,
)
from app.security.passwords import hash_password, verify_password


class AuthService:
    """Signup / signin against the users table with bcrypt password hashes."""

    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)
        self._employees = EmployeeRepository(db)

    def list_teams(self) -> TeamListResponse:
        teams = self._users.list_teams()
        options = [
            TeamOptionResponse(team_id=t.team_id, team_name=t.team_name)
            for t in teams
        ]
        return TeamListResponse(count=len(options), teams=options)

    def signup(self, body: SignupRequest) -> AuthUserResponse:
        display_name = body.username.strip()
        username = display_name.lower()
        team_name = body.team_name.strip()

        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

        if self._users.get_by_username(username) is not None:
            raise HTTPException(status_code=409, detail="That username is already taken")

        team = self._users.get_team_by_name(team_name)
        if team is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown team '{team_name}'. Choose a valid team such as HEB or TFG.",
            )

        user = self._users.create_user(
            username=username,
            password_hash=hash_password(body.password),
            team_id=team.team_id,
        )

        # Mirror signup into employees so the person is visible under their team.
        existing_employee = self._employees.get_employee_by_name_ci(team.team_id, display_name)
        if existing_employee is None:
            self._employees.create_employee(
                employee_name=display_name,
                team_id=team.team_id,
            )

        return AuthUserResponse(
            user_id=user.user_id,
            username=user.username,
            team_id=user.team_id,
            team_name=user.team.team_name,
        )

    def login(self, body: LoginRequest) -> AuthUserResponse:
        username = body.username.strip().lower()
        user = self._users.get_by_username(username)
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        return AuthUserResponse(
            user_id=user.user_id,
            username=user.username,
            team_id=user.team_id,
            team_name=user.team.team_name,
        )
