"""Load and normalize ppt_content.json into WsrContent."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.sprint_display import format_sprint_status_label, sprint_dates_from_section
from app.wsr_engine.models import ProjectContent, SprintSection, WsrContent


def _parse_iso(raw: object) -> date | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _normalize_section(section: dict, report_end: date | None) -> SprintSection:
    dates = sprint_dates_from_section(section)
    return SprintSection(
        sprint_name=section["sprint_name"],
        sprint_dates=dates,
        sprint_status=format_sprint_status_label(
            section.get("sprint_status"),
            sprint_end=_parse_iso(section.get("sprint_end_date")),
            report_end=report_end,
        ),
        completed=list(section.get("completed", [])),
        released=list(section.get("released", [])),
        inprogress=list(section.get("inprogress", [])),
    )


def _chunk_to_project(chunk: dict, report_end: date | None) -> ProjectContent:
    if chunk.get("sections"):
        sections = [_normalize_section(s, report_end) for s in chunk["sections"]]
    else:
        sections = [_normalize_section(chunk, report_end)]

    return ProjectContent(
        title=chunk["title"],
        project_key=chunk.get("project_key", ""),
        project_name=chunk.get("project_name", chunk["title"]),
        sections=sections,
        key_activities=list(chunk.get("key_activities", [])),
    )


def load_content(path: Path | str) -> WsrContent:
    p = Path(path)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("slides", data)
    report_end = _parse_iso(data.get("report_end_date"))
    projects = [_chunk_to_project(c, report_end) for c in chunks]

    return WsrContent(
        report_start_date=data.get("report_start_date", ""),
        report_end_date=data.get("report_end_date", ""),
        projects=projects,
    )


def section_display_content(section: SprintSection) -> dict:
    return section.to_display_dict()
