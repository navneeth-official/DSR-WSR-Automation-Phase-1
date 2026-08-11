"""Resolve active WSR template path."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.paths import G10X_TEMPLATE, REPO_ROOT, TEMPLATES_DIR

load_dotenv(REPO_ROOT / ".env")

WSR_TEMPLATE_FILENAME = "wsr_template.pptx"
LEGACY_G10X_TEMPLATE_NAME = G10X_TEMPLATE.name

_active_template: Path | None = None


def resolve_default_wsr_template() -> Path:
    primary = TEMPLATES_DIR / WSR_TEMPLATE_FILENAME
    if primary.is_file():
        return primary.resolve()
    if G10X_TEMPLATE.is_file():
        return G10X_TEMPLATE.resolve()
    raise FileNotFoundError(
        f"No WSR template found. Place {WSR_TEMPLATE_FILENAME} in {TEMPLATES_DIR}"
    )


def set_active_wsr_template(path: Path | str | None) -> None:
    global _active_template
    _active_template = Path(path).resolve() if path else None


def resolve_wsr_template(explicit: Path | str | None = None) -> Path:
    if explicit:
        p = Path(explicit).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"WSR template not found: {p}")
        return p
    if _active_template and _active_template.is_file():
        return _active_template
    env = os.environ.get("WSR_TEMPLATE_PATH", "").strip()
    if env:
        p = Path(env).resolve()
        if p.is_file():
            return p
    return resolve_default_wsr_template()
