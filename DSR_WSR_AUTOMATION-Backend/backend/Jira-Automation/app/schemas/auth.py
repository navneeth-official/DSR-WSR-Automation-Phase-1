from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100, description="Unique login username")
    password: str = Field(min_length=6, max_length=128, description="Plaintext password (hashed before storage)")
    team_name: str = Field(min_length=1, max_length=100, description="Team/account name, e.g. HEB or TFG")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    team_id: int
    team_name: str


class TeamOptionResponse(BaseModel):
    team_id: int
    team_name: str


class TeamListResponse(BaseModel):
    count: int
    teams: list[TeamOptionResponse]
