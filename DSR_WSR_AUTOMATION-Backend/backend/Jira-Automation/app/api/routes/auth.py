from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    SignupRequest,
    TeamListResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/teams", response_model=TeamListResponse)
def list_signup_teams(db: Session = Depends(get_db)) -> TeamListResponse:
    """List teams available for signup (HEB, TFG, etc.)."""
    return AuthService(db).list_teams()


@router.post("/signup", response_model=AuthUserResponse, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> AuthUserResponse:
    """Register a new user with a bcrypt-hashed password and team mapping."""
    return AuthService(db).signup(body)


@router.post("/login", response_model=AuthUserResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> AuthUserResponse:
    """Validate credentials and return the authenticated user (with team)."""
    return AuthService(db).login(body)
