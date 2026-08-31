from pydantic import BaseModel, ConfigDict, Field


class TrackCreateRequest(BaseModel):
    project_key: str = Field(description="Short track key, e.g. LOC or COST")
    project_name: str = Field(description="Display name, e.g. LOCO or Cost Core Service")
    is_active: bool = Field(default=True, description="Whether the track is active in the UI")


class TrackUpdateRequest(BaseModel):
    is_active: bool = Field(description="Whether the track is active in the UI")


class TrackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: int
    track_id: int = Field(description="Alias for project_id")
    project_key: str
    project_name: str
    is_active: bool


class TrackListResponse(BaseModel):
    count: int
    tracks: list[TrackResponse]
