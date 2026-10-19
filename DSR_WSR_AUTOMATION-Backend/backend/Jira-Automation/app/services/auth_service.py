from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
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
        self._db = db

    def list_teams(self) -> TeamListResponse:
        teams = self._users.list_teams()
        options = [
            TeamOptionResponse(team_id=t.team_id, team_name=t.team_name)
            for t in teams
        ]
        return TeamListResponse(count=len(options), teams=options)

    def signup(self, body: SignupRequest) -> AuthUserResponse:
        # ── 1. Normalise inputs ──────────────────────────────────────────────
        display_name = body.username.strip()   # preserved-case for employees table
        username = display_name.lower()         # lower-case for users table (login key)
        team_name = body.team_name.strip()

        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        if len(body.password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 6 characters long",
            )

        # ── 2. Resolve team (FK for both inserts) ────────────────────────────
        team = self._users.get_team_by_name(team_name)
        if team is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown team '{team_name}'. "
                    "Choose a valid team such as HEB or TFG."
                ),
            )

        # ── 3. Guard: username must be unique in users table ─────────────────
        if self._users.get_by_username(username) is not None:
            raise HTTPException(status_code=409, detail="That username is already taken")

        # ── 4. INSERT into users table ───────────────────────────────────────
        # Stores: username (lower), bcrypt password_hash, team_id (FK → teams),
        #         is_pmo flag, created_at, updated_at
        try:
            user = self._users.create_user(
                username=username,
                password_hash=hash_password(body.password),
                team_id=team.team_id,
                is_pmo=body.is_pmo,
            )
        except IntegrityError:
            self._db.rollback()
            raise HTTPException(status_code=409, detail="That username is already taken")

        # ── 5. INSERT into employees table ───────────────────────────────────
        # Stores: employee_name (display-case), team_id (FK → teams)
        # Only creates a new row when no case-insensitive match already exists
        # (prevents duplicates when an employee was pre-seeded before signing up).
        existing_employee = self._employees.get_employee_by_name_ci(
            team.team_id, display_name
        )
        if existing_employee is None:
            try:
                self._employees.create_employee(
                    employee_name=display_name,
                    team_id=team.team_id,
                )
            except Exception as exc:
                # User was already committed; surface a clear error rather than
                # silently succeeding with a broken employee record.
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Account created but failed to add employee record: {exc}. "
                        "Contact your administrator."
                    ),
                ) from exc

        # ── 6. Return the new user ───────────────────────────────────────────
        return AuthUserResponse(
            user_id=user.user_id,
            username=user.username,
            team_id=user.team_id,
            team_name=user.team.team_name,
            is_pmo=user.is_pmo,
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
            is_pmo=user.is_pmo,
        )
