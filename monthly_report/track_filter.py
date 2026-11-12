"""Resolve CLI track names to project keys and filter deck sections."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

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


def keys_for_track_name(
    track_name: str,
    *,
    sections_by_key: dict[str, ProjectSection],
) -> list[str]:
    """
    Map one CLI track token to ``project_key`` values using only DB-backed sections
  (``project_key`` and ``title`` = ``projects.project_name``).
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

    for section in sections_by_key.values():
        title_norm = _normalize(section.title)
        key_norm = _normalize(section.project_key)
        if needle == key_norm or needle == title_norm:
            add(section.project_key)

    if keys:
        return keys

    candidates: list[tuple[int, str]] = []
    for section in sections_by_key.values():
        title_norm = _normalize(section.title)
        key_norm = _normalize(section.project_key)
        score = max(
            fuzz.partial_ratio(needle, title_norm),
            fuzz.partial_ratio(needle, key_norm),
        )
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
    selected_keys: list[str] = []
    warnings: list[str] = []

    for track in track_names:
        matched = keys_for_track_name(track, sections_by_key=by_key)
        if not matched:
            warnings.append(
                f"Track {track!r} did not match any project with data "
                f"(use DB project_key or project_name from dry-run)."
            )
            continue
        for key in matched:
            if key not in selected_keys:
                selected_keys.append(key)

    filtered: list[ProjectSection] = [by_key[key] for key in selected_keys]

    if track_names and not filtered:
        warnings.append("No projects with data remain after applying --track-name filter.")

    return filtered, warnings
