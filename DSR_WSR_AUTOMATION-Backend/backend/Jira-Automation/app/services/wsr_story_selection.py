"""Pick one snapshot row per story for WSR generation."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.jira_story import JiraStory


def _snapshot_rank(story: JiraStory) -> tuple[date, date, datetime]:
    """Sort key for latest snapshot (snapshot_date, then updated_date, then created_at)."""
    snap = story.snapshot_date or date.min
    updated = story.updated_date or date.min
    created = story.created_at or datetime.min
    return (snap, updated, created)


def pick_wsr_snapshot_for_story(
    records: list[JiraStory],
    wsr_start: date,
    wsr_end: date,
) -> JiraStory:
    """
    Select the snapshot row to use for one story (``jira_key``).

    Case 1: If any ``snapshot_date`` falls within the WSR range (inclusive),
    return the record with the latest ``snapshot_date`` in that range.

    Case 2: Otherwise return the record with the latest snapshot overall.
    """
    if not records:
        raise ValueError("records must not be empty")

    in_range = [
        r
        for r in records
        if r.snapshot_date is not None and wsr_start <= r.snapshot_date <= wsr_end
    ]
    pool = in_range if in_range else records
    return max(pool, key=_snapshot_rank)


def select_wsr_story_snapshots(
    stories: list[JiraStory],
    wsr_start: date,
    wsr_end: date,
) -> list[JiraStory]:
    """
    Deduplicate stories by ``jira_key`` using WSR snapshot selection rules.

    Sprint filtering must already be applied — this only picks which snapshot
    row to use per unique story.
    """
    by_key: dict[str, list[JiraStory]] = defaultdict(list)
    for story in stories:
        by_key[story.jira_key].append(story)

    selected = [
        pick_wsr_snapshot_for_story(records, wsr_start, wsr_end)
        for records in by_key.values()
    ]
    selected.sort(
        key=lambda s: (
            s.project_id,
            s.sprint_id if s.sprint_id is not None else 0,
            s.jira_key,
        )
    )
    return selected
