from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.constants.story_status import STORY_STATUSES, resolve_status_id
from app.utils.date_parse import parse_flexible_date

FlexibleDate = Annotated[date | None, BeforeValidator(parse_flexible_date)]


class JiraStorySaveRequest(BaseModel):
    """Create or update a story using the frontend field names."""

    jira_key: str = Field(description="Jira Key")
    summary: str = Field(description="Summary")
    track: str = Field(description="Track project key or name, e.g. LOC or LOCO")
    sprint: str | None = Field(default=None, description="Sprint name")
    sprint_start_date: FlexibleDate = None
    sprint_end_date: FlexibleDate = None
    date_assigned: FlexibleDate = Field(default=None, description="Date Assigned")
    status: str = Field(
        description="Status; must map to a story_statuses name (To Do, In Progress, In Review, Done, Blocked)"
    )
    story_points: Decimal | None = Field(default=None, description="Story Points")
    percent_complete: Decimal | None = Field(
        default=None, ge=0, le=100, description="% Complete (0-100)"
    )
    assignee: str | None = Field(default=None, description="Assignee")
    reportee: str | None = Field(default=None, description="Reportee")
    comment: str | None = Field(
        default=None,
        description="Optional developer comment; omit from request to leave unchanged on update",
    )
    title: str | None = None
    description: str | None = None
    issue_type: str | None = None
    priority: str | None = None
    updated_date: FlexibleDate = None
    resolved_date: FlexibleDate = None
    snapshot_date: FlexibleDate = None

    @field_validator("status")
    @classmethod
    def _status_must_be_mapped(cls, value: str) -> str:
        if resolve_status_id(value) is None:
            allowed = ", ".join(name for _, name in STORY_STATUSES)
            raise ValueError(f"Status '{value}' cannot be mapped. Choose one of: {allowed}")
        return value


# POST /api/stories uses the same body shape.
JiraStoryCreateRequest = JiraStorySaveRequest


class JiraStoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jira_key: str
    project_id: int
    project_key: str
    project_name: str
    sprint_id: int | None
    sprint_name: str | None
    sprint_start_date: date | None
    sprint_end_date: date | None
    title: str | None
    summary: str
    description: str | None
    issue_type: str | None
    priority: str | None
    assignee: str | None
    reportee: str | None
    comment: str | None
    status: str
    story_points: Decimal | None
    percent_complete: Decimal | None
    date_assigned: date | None
    updated_date: date | None
    resolved_date: date | None
    snapshot_date: date | None


class JiraStoryListResponse(BaseModel):
    count: int
    stories: list[JiraStoryResponse]


class StoryCommentRequest(BaseModel):
    comment: str = Field(min_length=1, description="Developer comment for a new story version")


class TitleSuggestionsResponse(BaseModel):
    jira_key: str
    snapshot_date: date | None
    title: str | None = Field(
        default=None,
        description="Current title in the database (unchanged by suggest).",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="AI-generated title options from summary and description.",
    )
