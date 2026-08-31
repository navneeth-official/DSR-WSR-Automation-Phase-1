from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TrackSummary(BaseModel):
    project_id: int
    project_key: str
    project_name: str
    team_name: str


class SprintSummary(BaseModel):
    sprint_id: int
    sprint_name: str
    sprint_start_date: date | None
    sprint_end_date: date | None
    sprint_status: str


class DsrStoryRow(BaseModel):
    jira_key: str
    title: str
    date_assigned: date | None
    status: str
    story_points: Decimal | None
    percent_complete: Decimal | None
    assignee: str | None
    reportee: str | None = Field(description="Reporter from Jira / Rovo payload")
    comment: str | None = Field(default=None, description="Optional developer comment")


class DsrStatusSummary(BaseModel):
    total: int
    todo: int
    in_progress: int
    done: int
    completion_percent: int


class TrackDsrResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track: TrackSummary
    sprint: SprintSummary | None
    report_date: date
    summary: DsrStatusSummary
    stories: list[DsrStoryRow]


class TrackListItem(BaseModel):
    project_id: int
    project_key: str
    project_name: str
    is_active: bool = True


class TeamTracksResponse(BaseModel):
    team_name: str
    tracks: list[TrackListItem]
