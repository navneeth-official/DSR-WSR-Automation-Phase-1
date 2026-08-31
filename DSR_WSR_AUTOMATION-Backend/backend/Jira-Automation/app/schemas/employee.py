from pydantic import BaseModel, ConfigDict, Field


class EmployeeTrackResponse(BaseModel):
    """One employee-to-track assignment row."""

    model_config = ConfigDict(from_attributes=True)

    employee_id: int
    employee_name: str
    team_id: int
    team_name: str
    project_id: int = Field(description="Track project_id in the projects table")
    track_id: int = Field(description="Alias for project_id; tracks are stored as projects")
    project_key: str
    project_name: str
    is_active: bool


class EmployeeTrackListResponse(BaseModel):
    count: int
    employees: list[EmployeeTrackResponse]


class EmployeeCreateRequest(BaseModel):
    employee_name: str = Field(description="Full name of the employee")
    team_name: str = Field(description="Account/team name, e.g. HEB")
    project_id: int = Field(description="Track project_id to assign")
    is_active: bool = Field(default=True, description="Whether this track assignment is active")


class EmployeeTrackAssignRequest(BaseModel):
    project_id: int = Field(description="Track project_id to assign")
    is_active: bool = Field(default=True, description="Whether this track assignment is active")


class EmployeeTrackUpdateRequest(BaseModel):
    is_active: bool = Field(description="Set false to mark a track assignment as inactive")


class EmployeeDetailResponse(BaseModel):
    """Employee with all track assignments (for edit popover)."""

    employee_id: int
    employee_name: str
    team_id: int
    team_name: str
    tracks: list[EmployeeTrackResponse]
