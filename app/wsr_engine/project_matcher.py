"""Fuzzy project matching between content and template."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from rapidfuzz import fuzz

from app.wsr_engine.models import ProjectContent, TemplateModel

logger = logging.getLogger(__name__)

DEFAULT_ALIASES_PATH = Path(__file__).resolve().parents[2] / "config" / "wsr_aliases.json"
MATCH_THRESHOLD = 85


def _normalize_name(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[\u2013\u2014\-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def load_aliases(path: Path | str | None = None) -> dict[str, str]:
    p = Path(path) if path else DEFAULT_ALIASES_PATH
    if not p.is_file():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _score_match(content_name: str, template_name: str) -> int:
    a = _normalize_name(content_name)
    b = _normalize_name(template_name)
    if not a or not b:
        return 0
    if a == b or a in b or b in a:
        return 100
    return int(fuzz.token_set_ratio(a, b))


def match_projects(
    template: TemplateModel,
    content_projects: list[ProjectContent],
    aliases: dict[str, str] | None = None,
    threshold: int = MATCH_THRESHOLD,
) -> dict[str, ProjectContent]:
    aliases = dict(aliases or {})
    for proj in content_projects:
        if proj.project_name and proj.project_name not in aliases:
            aliases[proj.project_name] = proj.title
        if proj.title not in aliases:
            aliases[proj.title] = proj.title

    matched: dict[str, ProjectContent] = {}
    used_content: set[str] = set()

    for proj_map in template.projects:
        tmpl_name = proj_map.project_name
        candidates: list[tuple[int, ProjectContent, str]] = []

        alias_target = aliases.get(tmpl_name)
        if alias_target:
            for p in content_projects:
                if p.title == alias_target or p.project_name == alias_target:
                    candidates.append((100, p, alias_target))

        for proj in content_projects:
            if proj.title in used_content:
                continue
            for label in (proj.title, proj.project_name):
                if not label:
                    continue
                score = _score_match(label, tmpl_name)
                if score >= threshold:
                    candidates.append((score, proj, label))

        if not candidates:
            logger.warning("No content match for template project: %s", tmpl_name)
            continue

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_proj, label = candidates[0]
        matched[tmpl_name] = best_proj
        used_content.add(best_proj.title)
        logger.info(
            "Matched '%s' -> '%s' (score=%d via %s)",
            tmpl_name,
            best_proj.title,
            best_score,
            label,
        )

    return matched
