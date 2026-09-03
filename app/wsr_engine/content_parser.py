"""Load and normalize ppt_content.json into WsrContent."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.sprint_display import sprint_dates_from_section
from app.wsr_engine.models import ProjectContent, SprintSection, WsrContent


def _normalize_section(section: dict) -> SprintSection:
    dates = sprint_dates_from_section(section)
    start = section.get("sprint_start_date")
    end = section.get("sprint_end_date")
    return SprintSection(
        sprint_name=section["sprint_name"],
        sprint_dates=dates,
        sprint_status=section.get("sprint_status", "In-progress"),
        sprint_start_date=str(start) if start else None,
        sprint_end_date=str(end) if end else None,
        completed=list(section.get("completed", [])),
        released=list(section.get("released", [])),
        inprogress=list(section.get("inprogress", [])),
    )


def _chunk_to_project(chunk: dict) -> ProjectContent:
    if chunk.get("sections"):
        sections = [_normalize_section(s) for s in chunk["sections"]]
    else:
        sections = [_normalize_section(chunk)]

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
    projects = [_chunk_to_project(c) for c in chunks]

    return WsrContent(
        report_start_date=data.get("report_start_date", ""),
        report_end_date=data.get("report_end_date", ""),
        projects=projects,
    )


def section_display_content(section: SprintSection) -> dict:
    return section.to_display_dict()
