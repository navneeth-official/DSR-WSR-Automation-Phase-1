"""Resolve active WSR template path."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from app.paths import REPO_ROOT, TEMPLATES_DIR

load_dotenv(REPO_ROOT / ".env")

_active_template: Path | None = None


def list_templates_folder_pptx() -> list[Path]:
    """All usable .pptx files in templates/, newest first."""
    if not TEMPLATES_DIR.is_dir():
        return []
    files = [
        path.resolve()
        for path in TEMPLATES_DIR.glob("*.pptx")
        if path.is_file() and not path.name.startswith("~$")
    ]
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def resolve_default_wsr_template() -> Path:
    """Use the single placeholder template in ``templates/``, whatever its file name is."""
    folder_templates = list_templates_folder_pptx()
    if len(folder_templates) == 1:
        return folder_templates[0]
    if not folder_templates:
        raise FileNotFoundError(
            f"No WSR template found. Put the placeholder .pptx in {TEMPLATES_DIR}."
        )
    names = ", ".join(path.name for path in folder_templates)
    raise FileNotFoundError(
        f"{TEMPLATES_DIR} contains more than one PowerPoint file ({names}). "
        "Leave only the placeholder template in that folder."
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
