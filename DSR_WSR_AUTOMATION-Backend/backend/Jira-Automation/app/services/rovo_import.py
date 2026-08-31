from datetime import date
from decimal import Decimal

from app.repositories.jira_story_repository import JiraStoryRepository
from app.utils.date_parse import parse_flexible_date


def map_rovo_item_to_story_fields(item: dict) -> dict:
    """Map a single Rovo AI JSON object to jira_stories column values."""
    status = item.get("status", "Unknown")

    return {
        "jira_key": item["jira_key"],
        "project_key": item.get("project_key"),
        "project_name": item.get("project_name") or item.get("project_key", "Unknown"),
        "sprint_name": item.get("sprint_name"),
        "sprint_start_date": _parse_date(item.get("sprint_start_date")),
        "sprint_end_date": _parse_date(item.get("sprint_end_date")),
        "summary": item.get("summary", ""),
        "description": item.get("description"),
        "issue_type": item.get("issue_type"),
        "priority": item.get("priority"),
        "assignee": item.get("assignee"),
        "reporter": item.get("reporter"),
        "status": status,
        "story_points": item.get("story_points"),
        "created_date": _parse_date(item.get("created_date")),
        "updated_date": _parse_date(item.get("updated_date")),
        "resolved_date": _parse_date(item.get("resolved_date")),
        "snapshot_date": _parse_date(item.get("snapshot_date"))
        or _parse_date(item.get("updated_date"))
        or date.today(),
        "title": None,
        "completion": _infer_completion(status),
    }


def import_rovo_payload(
    repo: JiraStoryRepository,
    payload: list[dict],
) -> list[str]:
    """Import a list of Rovo JSON objects. Returns imported jira keys."""
    imported_keys: list[str] = []

    for item in payload:
        fields = map_rovo_item_to_story_fields(item)
        story = repo.upsert(**fields)
        repo.persist_generated_title(story)
        imported_keys.append(fields["jira_key"])

    return imported_keys


def _parse_date(value: str | None) -> date | None:
    return parse_flexible_date(value)


def _infer_completion(status: str) -> Decimal | None:
    """Rovo does not send completion %; infer a default from status."""
    normalized = status.strip().lower()
    if normalized in {"done", "closed", "resolved"}:
        return Decimal("100")
    if normalized in {"in progress", "in review", "in development"}:
        return Decimal("50")
    return Decimal("0")


def infer_completion(status: str) -> Decimal | None:
    return _infer_completion(status)
