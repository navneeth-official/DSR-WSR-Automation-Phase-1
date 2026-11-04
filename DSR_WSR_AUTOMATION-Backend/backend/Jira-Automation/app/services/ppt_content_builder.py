"""Build structured PPT slide content from jira_stories + projects + sprints."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.constants.ppt_mapping import (
    PPT_SLIDE_ORDER,
    PPT_SLIDE_TITLES,
    STATUS_TO_BUCKET,
)
from app.constants.story_status import normalize_status_text
from app.models.jira_story import JiraStory
from app.repositories.jira_story_repository import JiraStoryRepository
from app.services.sprint_display import format_sprint_dates_for_display, format_sprint_status_label


def _strip_trailing_ellipsis(text: str) -> str:
    """Drop a truncation marker so slide bullets are not suffixed with ``...``."""
    cleaned = text.strip()
    while cleaned.endswith("..."):
        cleaned = cleaned[:-3].rstrip()
    while cleaned.endswith("\u2026"):
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def _ppt_story_line(story: JiraStory) -> str:
    """Use the persisted DB title; fall back to summary only for the slide (no LLM)."""
    title = _strip_trailing_ellipsis(story.title or "")
    if title:
        return title
    return _strip_trailing_ellipsis(story.summary or "")


def _title_usage_stats(stories: list[JiraStory]) -> tuple[int, int]:
    """Return (titles_from_db, titles_fallback_summary)."""
    from_db = 0
    fallback = 0
    for story in stories:
        if (story.title or "").strip():
            from_db += 1
        else:
            fallback += 1
    return from_db, fallback


def ppt_slide_title(project_key: str, project_name: str) -> str:
    return PPT_SLIDE_TITLES.get(project_key, project_name)


def _sprint_status_label(
    db_status: str | None,
    *,
    sprint_end: date | None = None,
    report_end: date | None = None,
) -> str:
    """``In-progress`` only when the sprint continues past the WSR week; otherwise ``Ended``."""
    return format_sprint_status_label(
        db_status,
        sprint_end=sprint_end,
        report_end=report_end,
    )


def _bucket_story(status: str | None) -> str | None:
    """Map a story status to a WSR bucket. Statuses other than In Progress, In Review, and Done are omitted."""
    return STATUS_TO_BUCKET.get(normalize_status_text(status))


def key_activities_from_inprogress(sections: list[dict[str, Any]]) -> list[str]:
    """Mirror HL 'Stories in-progress this week' bullets in the KA tab."""
    items: list[str] = []
    seen: set[str] = set()
    for section in sections:
        for story in section.get("inprogress") or []:
            text = str(story).strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                items.append(text)
    return items


def _slide_order_key(project_key: str) -> tuple[int, str]:
    try:
        return (PPT_SLIDE_ORDER.index(project_key), project_key)
    except ValueError:
        return (len(PPT_SLIDE_ORDER), project_key)


def _sprint_section_order(sprint_status: str) -> int:
    """Within a project slide, list In-progress sprints before Ended."""
    if sprint_status == "In-progress":
        return 0
    return 1


def _date_desc_nulls_last(value: date | None) -> tuple[int, int]:
    """Sort key fragment: latest dates first; missing dates last."""
    if value is None:
        return (1, 0)
    return (0, -value.toordinal())


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _sprint_within_status_sort_key(chunk: dict[str, Any]) -> tuple[int, int, str]:
    """Among sprints with the same status: latest start (in-progress) or end (ended) first."""
    sprint_start = _parse_iso_date(chunk.get("sprint_start_date"))
    sprint_end = _parse_iso_date(chunk.get("sprint_end_date"))
    if chunk.get("sprint_status") == "In-progress":
        date_key = _date_desc_nulls_last(sprint_start)
    else:
        date_key = _date_desc_nulls_last(sprint_end)
    return (*date_key, chunk.get("sprint_name", ""))


def build_slide_chunks(
    stories: list[JiraStory],
    *,
    report_end: date | None = None,
) -> list[dict[str, Any]]:
    """
    Group stories by (project, sprint) and build one JSON chunk per group.

    Sprint line dates always come from ``sprints.sprint_start_date`` /
    ``sprints.sprint_end_date`` (full DB values). WSR range is not used here.
    """
    groups: dict[tuple[int, int | None], list[JiraStory]] = defaultdict(list)
    for story in stories:
        groups[(story.project_id, story.sprint_id)].append(story)

    chunks: list[dict[str, Any]] = []

    for (project_id, sprint_id), group_stories in groups.items():
        project = group_stories[0].project
        sprint = group_stories[0].sprint
        project_key = project.project_key
        project_name = project.project_name

        released: list[str] = []
        inprogress: list[str] = []
        completed: list[str] = []

        for story in sorted(group_stories, key=lambda s: s.jira_key):
            title = _ppt_story_line(story)
            bucket = _bucket_story(story.status)
            if bucket == "released":
                released.append(title)
            elif bucket == "inprogress":
                inprogress.append(title)
            elif bucket == "completed":
                completed.append(title)

        if not released and not inprogress and not completed:
            continue

        sprint_name = sprint.sprint_name if sprint else "Current Sprint"
        sprint_start = sprint.sprint_start_date if sprint else None
        sprint_end = sprint.sprint_end_date if sprint else None
        sprint_dates = format_sprint_dates_for_display(sprint_start, sprint_end)
        status_word = _sprint_status_label(
            sprint.sprint_status if sprint else None,
            sprint_end=sprint_end,
            report_end=report_end,
        )

        section_payload = {
            "sprint_name": sprint_name,
            "sprint_start_date": sprint_start.isoformat() if sprint_start else None,
            "sprint_end_date": sprint_end.isoformat() if sprint_end else None,
            "sprint_dates": sprint_dates,
            "sprint_status": status_word,
            "released": released,
            "inprogress": inprogress,
            "completed": completed,
        }
        chunks.append(
            {
                "project_key": project_key,
                "project_name": project_name,
                "title": ppt_slide_title(project_key, project_name),
                "key_activities": key_activities_from_inprogress([section_payload]),
                **section_payload,
            }
        )

    chunks.sort(
        key=lambda c: (
            _slide_order_key(c["project_key"]),
            _sprint_section_order(c["sprint_status"]),
            _sprint_within_status_sort_key(c),
        )
    )
    return chunks


def group_chunks_by_slide_title(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Group (project, sprint) chunks that share the same PPT slide title.
    Each sprint stays a separate section with its own sprint line (G10X Supplier pattern).
    """
    by_title: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for chunk in chunks:
        title = chunk["title"]
        section = {
            "sprint_name": chunk["sprint_name"],
            "sprint_start_date": chunk.get("sprint_start_date"),
            "sprint_end_date": chunk.get("sprint_end_date"),
            "sprint_dates": chunk["sprint_dates"],
            "sprint_status": chunk["sprint_status"],
            "released": list(chunk["released"]),
            "inprogress": list(chunk["inprogress"]),
            "completed": list(chunk["completed"]),
        }
        if title not in by_title:
            by_title[title] = {
                "project_key": chunk["project_key"],
                "project_name": chunk["project_name"],
                "title": title,
                "sections": [],
                "key_activities": [],
            }
            order.append(title)
        by_title[title]["sections"].append(section)

    for title in order:
        by_title[title]["key_activities"] = key_activities_from_inprogress(
            by_title[title]["sections"]
        )

    return [by_title[t] for t in order]


# Backward-compatible alias
merge_chunks_by_title = group_chunks_by_slide_title


def build_ppt_content(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    merge_titles: bool = True,
    save_titles: bool = False,
    regenerate_titles: bool = False,
) -> dict[str, Any]:
    """
    Full pipeline: fetch stories for WSR date range and return JSON for PPT build.

    Story bullet text uses ``jira_stories.title`` from the database. By default,
    titles are expected to be created during intake; missing titles fall back to
    summary on the slide only (no LLM calls). Use ``save_titles`` or
    ``regenerate_titles`` to invoke title generation via ``ensure_story_titles``.

    Sprint selection uses overlap against ``start_date``/``end_date`` (unchanged).
    One snapshot per ``jira_key`` is chosen (latest in-range, else latest overall).
    Sprint dates on each slide are the full ``sprints`` table values, never clipped
    to the WSR window.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must be on or before end_date ({end_date})."
        )

    repo = JiraStoryRepository(db)
    stories = repo.get_for_wsr_date_range(start_date, end_date)
    if not stories:
        raise ValueError(
            f"No stories found for report period {start_date} to {end_date}."
        )

    titles_generated = 0
    titles_reused = 0
    if save_titles or regenerate_titles:
        from app.services.title_generator import ensure_story_titles

        titles_generated, titles_reused = ensure_story_titles(
            stories,
            save=save_titles,
            db=db if save_titles else None,
            regenerate=regenerate_titles,
        )
        if save_titles:
            db.commit()

    titles_from_db, titles_fallback_summary = _title_usage_stats(stories)
    if not save_titles and not regenerate_titles:
        titles_generated = 0
        titles_reused = titles_from_db

    chunks = build_slide_chunks(stories, report_end=end_date)
    if merge_titles:
        slides = merge_chunks_by_title(chunks)
    else:
        slides = chunks

    return {
        "report_start_date": start_date.isoformat(),
        "report_end_date": end_date.isoformat(),
        "slides": slides,
        "meta": {
            "story_count": len(stories),
            "slide_count": len(slides),
            "titles_from_db": titles_from_db,
            "titles_fallback_summary": titles_fallback_summary,
            "titles_generated": titles_generated,
            "titles_reused": titles_reused,
        },
    }
