"""Repository path constants for templates, scripts, and generated outputs."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "templates"
OUTPUT_DIR = REPO_ROOT / "output"
DATA_DIR = REPO_ROOT / "data"
SCRIPTS_DIR = REPO_ROOT / "scripts"

G10X_TEMPLATE_NAME = "G10X H-E-B WSR Sustainment 05 June 2026 .pptx"
G10X_TEMPLATE = TEMPLATES_DIR / G10X_TEMPLATE_NAME
GENERIC_WSR_TEMPLATE_NAME = (
    "G10X H-E-B WSR Haskell Location Pharmacy GSS PAM 01 Aug 2025- Generic Template.pptx"
)
GENERIC_WSR_TEMPLATE = TEMPLATES_DIR / GENERIC_WSR_TEMPLATE_NAME
PPT_BUILDER = SCRIPTS_DIR / "update_delivery_status.py"

DEFAULT_CONTENT_JSON = OUTPUT_DIR / "ppt_content.json"
DEFAULT_CONTENT_PREVIEW = OUTPUT_DIR / "ppt_content_preview.txt"
DEFAULT_PPT_OUTPUT = OUTPUT_DIR / "HEB_Delivery_Status.pptx"
GEOMETRY_DEBUG_LOG = OUTPUT_DIR / "layout_geometry_debug.log"


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
