from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

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
    status: str = Field(description="Status")
    story_points: Decimal | None = Field(default=None, description="Story Points")
    percent_complete: Decimal | None = Field(default=None, description="% Complete")
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
