"""Paths and settings for the monthly cadence report."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
MONTHLY_TEMPLATES_DIR = REPO_ROOT / "templates" / "monthly"
MONTHLY_OUTPUT_DIR = REPO_ROOT / "output" / "monthly"
PROJECT_ORDER_FILE = REPO_ROOT / "config" / "monthly_project_order.json"
DEFAULT_INDEX_REFERENCE = (
    REPO_ROOT / "templates" / "G10X H-E-B WSR Haskell Location Pharmacy GSS PAM 01 Aug 2025 Generic Template.pptx"
)

load_dotenv(REPO_ROOT / ".env")


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def database_url() -> str:
    url = _env("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example)")
    return url


def resolve_template(explicit: str | Path | None = None) -> Path:
    """Explicit path, else MSR_TEMPLATE_PATH, else newest .pptx in templates/monthly/."""
    candidate = explicit or _env("MSR_TEMPLATE_PATH")
    if candidate:
        path = _repo_path(candidate)
        if not path.is_file():
            raise FileNotFoundError(f"Monthly template not found: {path}")
        return path

    templates = sorted(
        (
            p
            for p in MONTHLY_TEMPLATES_DIR.glob("*.pptx")
            if p.is_file() and not p.name.startswith("~$")
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not templates:
        raise FileNotFoundError(f"No monthly template found in {MONTHLY_TEMPLATES_DIR}")
    return templates[0]


def output_dir() -> Path:
    configured = _env("MSR_OUTPUT_DIR")
    return _repo_path(configured) if configured else MONTHLY_OUTPUT_DIR


def project_order_keys() -> list[str]:
    if not PROJECT_ORDER_FILE.is_file():
        return []
    data = json.loads(PROJECT_ORDER_FILE.read_text(encoding="utf-8"))
    return [str(key) for key in data]


def resolve_index_reference(explicit: str | Path | None = None) -> Path:
    candidate = explicit or _env("MSR_INDEX_REFERENCE")
    if candidate:
        path = _repo_path(candidate)
        if not path.is_file():
            raise FileNotFoundError(f"Index reference template not found: {path}")
        return path
    if DEFAULT_INDEX_REFERENCE.is_file():
        return DEFAULT_INDEX_REFERENCE
    raise FileNotFoundError(
        "No index reference template. Set MSR_INDEX_REFERENCE or add the WSR template under templates/."
    )


def default_output_path(meeting_date) -> Path:
    return output_dir() / f"HEB_Monthly_Cadence_{meeting_date.isoformat()}.pptx"


def project_display_name(project_key: str, project_name: str) -> str:
    """Deck-facing project title from the database (``projects.project_name``)."""
    del project_key
    return (project_name or "").strip()
