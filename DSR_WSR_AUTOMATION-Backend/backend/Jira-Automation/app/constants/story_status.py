"""Canonical story statuses (mirrors the ``story_statuses`` lookup table).

``jira_stories.status_id`` references these ids. Keep this file and migration
``018_story_status_lookup`` in sync.
"""

import re

STATUS_TODO = 1
STATUS_IN_PROGRESS = 2
STATUS_IN_REVIEW = 3
STATUS_DONE = 4
STATUS_BLOCKED = 5

# (status_id, status_name) in display order.
STORY_STATUSES: tuple[tuple[int, str], ...] = (
    (STATUS_TODO, "To Do"),
    (STATUS_IN_PROGRESS, "In Progress"),
    (STATUS_IN_REVIEW, "In Review"),
    (STATUS_DONE, "Done"),
    (STATUS_BLOCKED, "Blocked"),
)

STATUS_NAME_BY_ID: dict[int, str] = dict(STORY_STATUSES)

# Normalised alias (lower-case, separators collapsed to one space) -> status id.
_ALIASES: dict[str, int] = {
    "to do": STATUS_TODO,
    "todo": STATUS_TODO,
    "open": STATUS_TODO,
    "backlog": STATUS_TODO,
    "new": STATUS_TODO,
    "reopened": STATUS_TODO,
    "selected for development": STATUS_TODO,
    "in progress": STATUS_IN_PROGRESS,
    "inprogress": STATUS_IN_PROGRESS,
    "in development": STATUS_IN_PROGRESS,
    "wip": STATUS_IN_PROGRESS,
    "active": STATUS_IN_PROGRESS,
    "in review": STATUS_IN_REVIEW,
    "inreview": STATUS_IN_REVIEW,
    "review": STATUS_IN_REVIEW,
    "code review": STATUS_IN_REVIEW,
    "ready for qa": STATUS_IN_REVIEW,
    "in qa": STATUS_IN_REVIEW,
    "in testing": STATUS_IN_REVIEW,
    "done": STATUS_DONE,
    "closed": STATUS_DONE,
    "resolved": STATUS_DONE,
    "complete": STATUS_DONE,
    "completed": STATUS_DONE,
    "blocked": STATUS_BLOCKED,
    "on hold": STATUS_BLOCKED,
    "impediment": STATUS_BLOCKED,
}


def normalize_status_text(raw: str | None) -> str:
    return re.sub(r"[\s_\-]+", " ", (raw or "").strip().lower())


def resolve_status_id(raw: str | int | None) -> int | None:
    """Map free text (or an existing id) to a ``story_statuses.status_id``.

    Unknown or empty values return ``None``.
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw in STATUS_NAME_BY_ID else None
    return _ALIASES.get(normalize_status_text(raw))


def resolve_status_id_or_default(raw: str | int | None) -> int:
    """Like :func:`resolve_status_id` but falls back to ``To Do`` (for scripts/imports).

    The API rejects unmappable statuses; the intake UI makes the user pick one.
    """
    resolved = resolve_status_id(raw)
    return STATUS_TODO if resolved is None else resolved


def status_name(status_id: int | None) -> str:
    return STATUS_NAME_BY_ID.get(status_id or 0, STATUS_NAME_BY_ID[STATUS_TODO])
