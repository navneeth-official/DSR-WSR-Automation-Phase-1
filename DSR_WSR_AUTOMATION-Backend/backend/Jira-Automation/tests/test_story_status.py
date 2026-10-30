import pytest
from pydantic import ValidationError

from app.constants.story_status import (
    STATUS_BLOCKED,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_IN_REVIEW,
    STATUS_TODO,
    resolve_status_id,
    resolve_status_id_or_default,
    status_name,
)
from app.models.jira_story import JiraStory
from app.schemas.jira_story import JiraStorySaveRequest


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("To Do", STATUS_TODO),
        ("todo", STATUS_TODO),
        ("In-Progress", STATUS_IN_PROGRESS),
        ("IN_PROGRESS", STATUS_IN_PROGRESS),
        ("In Review", STATUS_IN_REVIEW),
        ("in-review", STATUS_IN_REVIEW),
        ("Done", STATUS_DONE),
        ("Closed", STATUS_DONE),
        ("Blocked", STATUS_BLOCKED),
    ],
)
def test_known_statuses_map_to_ids(raw: str, expected: int) -> None:
    assert resolve_status_id(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "Unknown", "Weird Status", 99])
def test_unmapped_statuses_resolve_to_none(raw) -> None:
    assert resolve_status_id(raw) is None
    assert resolve_status_id_or_default(raw) == STATUS_TODO


def test_status_name() -> None:
    assert status_name(STATUS_DONE) == "Done"
    assert status_name(None) == "To Do"


def test_model_status_property() -> None:
    story = JiraStory(status_id=STATUS_IN_REVIEW)
    assert story.status == "In Review"


def test_save_request_accepts_mapped_status() -> None:
    body = JiraStorySaveRequest(jira_key="X-1", summary="s", track="LOC", status="in-progress")
    assert body.status == "in-progress"


@pytest.mark.parametrize("raw", ["Weird Status", "", "Unknown"])
def test_save_request_rejects_unmapped_status(raw: str) -> None:
    with pytest.raises(ValidationError) as exc:
        JiraStorySaveRequest(jira_key="X-1", summary="s", track="LOC", status=raw)
    assert "cannot be mapped" in str(exc.value)
