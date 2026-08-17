"""Detect skeleton vs fixed WSR templates."""

from __future__ import annotations

import re

from app.wsr_engine.models import TemplateModel

_PLACEHOLDER_PATTERNS = (
    r"\{[^}]+\}",
    r"track name",
    r"service name",
    r"sprint name",
    r"\{track",
)


def is_placeholder_name(name: str) -> bool:
    text = (name or "").strip().lower()
    if not text:
        return True
    for pattern in _PLACEHOLDER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def is_skeleton_template(model: TemplateModel) -> bool:
    """True when the template ships a single prototype delivery slide instead of all projects."""
    if not model.projects:
        return False

    real_projects = [p for p in model.projects if not is_placeholder_name(p.project_name)]
    if len(model.projects) == 1 and is_placeholder_name(model.projects[0].project_name):
        return True
    return len(real_projects) == 0 and len(model.projects) <= 1
