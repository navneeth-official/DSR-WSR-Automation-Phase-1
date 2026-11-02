"""Resolve CLI track names to project keys and filter deck sections."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

from monthly_report.config import PROJECT_NAMES_FILE

if TYPE_CHECKING:
    from monthly_report.deck import ProjectSection

_MATCH_THRESHOLD = 85


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def parse_track_names(cli_values: list[str] | None, env_value: str) -> list[str]:
    """Split comma-separated tokens; preserve order; drop empties."""
    raw: list[str] = []
    if cli_values:
        for value in cli_values:
            raw.extend(part.strip() for part in value.split(","))
    elif env_value.strip():
        raw.extend(part.strip() for part in env_value.split(","))
    seen: set[str] = set()
    ordered: list[str] = []
    for name in raw:
        if not name:
            continue
        key = _normalize(name)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(name)
    return ordered


def _configured_display_names() -> dict[str, str]:
    if not PROJECT_NAMES_FILE.is_file():
        return {}
    return json.loads(PROJECT_NAMES_FILE.read_text(encoding="utf-8"))


def keys_for_track_name(
    track_name: str,
    *,
    sections_by_key: dict[str, ProjectSection],
    display_names: dict[str, str],
) -> list[str]:
    """
    Map one user track name to one or more project keys (e.g. SUP and SPUR share a label).
    """
    needle = _normalize(track_name)
    if not needle:
        return []

    keys: list[str] = []
    seen: set[str] = set()

    def add(key: str) -> None:
        if key not in seen:
            seen.add(key)
            keys.append(key)

    for key, display in display_names.items():
        display_norm = _normalize(display)
        if needle == _normalize(key) or needle == display_norm:
            add(key)

    for section in sections_by_key.values():
        title_norm = _normalize(section.title)
        key_norm = _normalize(section.project_key)
        if needle == key_norm or needle == title_norm:
            add(section.project_key)

    if keys:
        return keys

    candidates: list[tuple[int, str]] = []
    for key, display in display_names.items():
        display_norm = _normalize(display)
        score = max(
            fuzz.partial_ratio(needle, display_norm),
            fuzz.partial_ratio(needle, _normalize(key)),
        )
        if score >= _MATCH_THRESHOLD:
            candidates.append((score, key))
    for section in sections_by_key.values():
        title_norm = _normalize(section.title)
        score = fuzz.partial_ratio(needle, title_norm)
        if score >= _MATCH_THRESHOLD:
            candidates.append((score, section.project_key))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    for _score, key in candidates:
        add(key)
    return keys


def filter_sections_by_track_names(
    sections: list[ProjectSection],
    track_names: list[str],
) -> tuple[list[ProjectSection], list[str]]:
    """
    Keep only projects selected by ``track_names`` (in command order).

    Returns (filtered_sections, warnings).
    """
    if not track_names:
        return list(sections), []

    by_key = {section.project_key: section for section in sections}
    display_names = _configured_display_names()
    selected_keys: list[str] = []
    warnings: list[str] = []

    for track in track_names:
        matched = keys_for_track_name(
            track,
            sections_by_key=by_key,
            display_names=display_names,
        )
        if not matched:
            warnings.append(f"Track name {track!r} did not match any configured project.")
            continue
        for key in matched:
            if key not in selected_keys:
                selected_keys.append(key)

    filtered: list[ProjectSection] = []
    for key in selected_keys:
        section = by_key.get(key)
        if section is None:
            label = display_names.get(key, key)
            warnings.append(
                f"Track {label!r} ({key}) has no sprint/story data in the report month."
            )
            continue
        filtered.append(section)

    if track_names and not filtered:
        warnings.append("No projects with data remain after applying --track-name filter.")

    return filtered, warnings
