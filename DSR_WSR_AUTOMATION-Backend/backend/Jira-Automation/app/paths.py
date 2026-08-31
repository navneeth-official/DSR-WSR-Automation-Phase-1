"""Repository path constants for templates, scripts, and generated outputs."""

from __future__ import annotations

from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "templates"
OUTPUT_DIR = REPO_ROOT / "output"
DATA_DIR = REPO_ROOT / "data"
SCRIPTS_DIR = REPO_ROOT / "scripts"

G10X_TEMPLATE_NAME = "G10X H-E-B WSR Sustainment 05 June 2026 .pptx"
G10X_TEMPLATE = TEMPLATES_DIR / G10X_TEMPLATE_NAME
UPLOADED_WSR_TEMPLATE_FILENAME = "WSR_UPLOADED_TEMPLATE.pptx"
UPLOADED_WSR_TEMPLATE_PPT = OUTPUT_DIR / UPLOADED_WSR_TEMPLATE_FILENAME
UPLOADED_WSR_TEMPLATE_META = OUTPUT_DIR / "WSR_UPLOADED_TEMPLATE.json"
WSR_TEMPLATES_DIR = OUTPUT_DIR / "wsr_templates"
WSR_TEMPLATE_DRAFT_FILENAME = "WSR_TEMPLATE_DRAFT.pptx"
WSR_TEMPLATE_DRAFT_PPT = OUTPUT_DIR / WSR_TEMPLATE_DRAFT_FILENAME
WSR_TEMPLATE_DRAFT_META = OUTPUT_DIR / "WSR_TEMPLATE_DRAFT.json"
PPT_BUILDER = SCRIPTS_DIR / "update_delivery_status.py"

DEFAULT_CONTENT_JSON = OUTPUT_DIR / "ppt_content.json"
DEFAULT_CONTENT_PREVIEW = OUTPUT_DIR / "ppt_content_preview.txt"
DEFAULT_PPT_OUTPUT = OUTPUT_DIR / "HEB_Delivery_Status.pptx"
GEOMETRY_DEBUG_LOG = OUTPUT_DIR / "layout_geometry_debug.log"


class WsrOutputPaths:
    def __init__(self, json_path: Path, preview_path: Path, ppt_path: Path) -> None:
        self.json_path = json_path
        self.preview_path = preview_path
        self.ppt_path = ppt_path


def wsr_variant_suffix(variant: int) -> str:
    """Filename suffix for alternate WSR decks (v1 has no suffix)."""
    if variant <= 1:
        return ""
    return f"_v{variant}"


def wsr_output_paths(start_date: date, end_date: date, *, variant: int = 1) -> WsrOutputPaths:
    """Per-week output files under output/. Variant 2+ uses _v2, _v3, … suffixes."""
    stem = (
        f"WSR_{start_date.isoformat()}_{end_date.isoformat()}"
        f"{wsr_variant_suffix(variant)}"
    )
    return WsrOutputPaths(
        json_path=OUTPUT_DIR / f"{stem}.json",
        preview_path=OUTPUT_DIR / f"{stem}_preview.txt",
        ppt_path=OUTPUT_DIR / f"{stem}.pptx",
    )


def wsr_preview_dir(start_date: date, end_date: date, *, variant: int = 1) -> Path:
    """Directory for rendered PNG previews of a WSR deck."""
    stem = (
        f"WSR_{start_date.isoformat()}_{end_date.isoformat()}"
        f"{wsr_variant_suffix(variant)}"
    )
    return OUTPUT_DIR / f"{stem}_slides"


def wsr_manifest_path(start_date: date, end_date: date) -> Path:
    """JSON manifest listing all generated variants for a report week."""
    stem = f"WSR_{start_date.isoformat()}_{end_date.isoformat()}"
    return OUTPUT_DIR / f"{stem}_manifest.json"


def uploaded_wsr_template_preview_dir() -> Path:
    """Directory for rendered PNG previews of the legacy uploaded WSR template."""
    return OUTPUT_DIR / "WSR_UPLOADED_TEMPLATE_slides"


def wsr_template_preview_dir(template_id: str) -> Path:
    """Directory for rendered PNG previews of a saved WSR template."""
    return WSR_TEMPLATES_DIR / f"{template_id}_slides"


def wsr_template_draft_preview_dir() -> Path:
    """Directory for rendered PNG previews of a staged (unsaved) WSR template."""
    return OUTPUT_DIR / "WSR_TEMPLATE_DRAFT_slides"


def wsr_template_ppt_path(template_id: str) -> Path:
    return WSR_TEMPLATES_DIR / f"{template_id}.pptx"


def wsr_template_meta_path(template_id: str) -> Path:
    return WSR_TEMPLATES_DIR / f"{template_id}.json"


def ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def evaluation_report_paths(ppt_path: Path) -> tuple[Path, Path, Path]:
    """User JSON, user text, and internal debug JSON paths under output/."""
    ensure_output_dir()
    stem = Path(ppt_path).stem
    return (
        OUTPUT_DIR / f"{stem}.format_eval.json",
        OUTPUT_DIR / f"{stem}.format_eval.txt",
        OUTPUT_DIR / f"{stem}.format_eval.internal.json",
    )


def evaluation_ai_report_paths(ppt_path: Path) -> tuple[Path, Path]:
    """Visual AI review JSON + text paths under output/."""
    ensure_output_dir()
    stem = Path(ppt_path).stem
    return (
        OUTPUT_DIR / f"{stem}.format_eval.ai.json",
        OUTPUT_DIR / f"{stem}.format_eval.ai.txt",
    )
