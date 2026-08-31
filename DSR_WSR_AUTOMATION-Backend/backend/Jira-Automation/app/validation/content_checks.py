"""Compare extracted deck content against ppt_content.json."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.ppt_format_violations import _service_base_title


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _story_lines(slide: dict[str, Any]) -> list[str]:
    hl = slide.get("highlights") or {}
    lines: list[str] = []
    for para in hl.get("paragraphs") or []:
        role = para.get("role")
        text = (para.get("text") or "").strip()
        if not text or role != "story_item":
            continue
        lines.append(text.lstrip("-• ").strip())
    return lines


def _expected_stories(project: dict[str, Any]) -> list[str]:
    stories: list[str] = []
    for section in project.get("sections") or []:
        for bucket in ("completed", "released", "inprogress"):
            stories.extend(section.get(bucket) or [])
    return stories


def _project_has_ka_content(project: dict[str, Any]) -> bool:
    ka_items = project.get("key_activities") or []
    return any(str(item).strip() for item in ka_items)


def _ka_leftover_text(slide: dict[str, Any]) -> list[str]:
    ka = slide.get("key_activities")
    if not ka:
        return []
    leftovers: list[str] = []
    for para in ka.get("content_paragraphs") or []:
        text = (para.get("text") or "").strip()
        if text:
            leftovers.append(text)
    return leftovers


def _match_story(expected: str, deck_lines: list[str]) -> bool:
    needle = _norm(expected)
    if not needle:
        return True
    for line in deck_lines:
        hay = _norm(line)
        if needle in hay or hay in needle:
            return True
    return False


def _index_deck_slides(deck_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for slide in deck_data.get("slides", []):
        base = _service_base_title(slide.get("title", ""))
        bucket = grouped.setdefault(
            base.lower(),
            {"main": None, "contd": [], "all_stories": []},
        )
        stories = _story_lines(slide)
        bucket["all_stories"].extend(stories)
        if slide.get("is_contd"):
            bucket["contd"].append(slide)
        else:
            bucket["main"] = slide
    return grouped


def load_content_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def detect_content_violations(
    deck_data: dict[str, Any],
    content: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return CONTENT-* violations comparing deck text to ppt_content.json."""
    violations: list[dict[str, Any]] = []
    deck_by_project = _index_deck_slides(deck_data)

    for project in content.get("slides") or []:
        title = str(project.get("title") or project.get("project_name") or "")
        if not title:
            continue
        key = title.lower()
        deck_entry = deck_by_project.get(key)
        expected = _expected_stories(project)

        if not deck_entry or deck_entry["main"] is None:
            violations.append(
                {
                    "rule_id": "CONTENT-PRJ-01",
                    "severity": "critical",
                    "slide_index": None,
                    "title": f"Delivery status – {title}",
                    "message": f"Project '{title}' from ppt_content.json has no main slide in the deck",
                    "project": title,
                }
            )
            continue

        deck_stories = deck_entry["all_stories"]
        for story in expected:
            if not _match_story(story, deck_stories):
                main = deck_entry["main"]
                violations.append(
                    {
                        "rule_id": "CONTENT-HL-02",
                        "severity": "critical",
                        "slide_index": main.get("slide_index"),
                        "title": main.get("title", ""),
                        "message": (
                            "Story from ppt_content.json not found on slide: "
                            f"'{story[:120]}'"
                        ),
                        "project": title,
                        "story": story,
                    }
                )

        if not _project_has_ka_content(project):
            slides_to_check = [deck_entry["main"], *deck_entry["contd"]]
            for slide in slides_to_check:
                if slide is None:
                    continue
                leftovers = _ka_leftover_text(slide)
                if not leftovers:
                    continue
                sample = leftovers[0]
                violations.append(
                    {
                        "rule_id": "CONTENT-KA-01",
                        "severity": "critical",
                        "slide_index": slide.get("slide_index"),
                        "title": slide.get("title", ""),
                        "message": (
                            "KA content cell contains leftover text; expected empty placeholders"
                        ),
                        "sample_text": sample[:160],
                        "project": title,
                    }
                )

    return violations
