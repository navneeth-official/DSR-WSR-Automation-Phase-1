"""Generate WSR PowerPoint decks from PostgreSQL story data."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.paths import OUTPUT_DIR, ensure_output_dir, wsr_preview_dir
from app.services.ppt_content_builder import build_ppt_content
from app.services.ppt_content_preview import format_content_preview
from app.services.wsr_preview_service import export_wsr_slide_previews
from app.services.cloud_upload_service import (
    cloud_response_fields,
    cloud_response_fields_from_upload,
    try_upload_wsr_ppt,
)
from app.services.wsr_template_upload_service import resolve_template_path
from app.services.wsr_variant_service import (
    WSR_PPTX_RE,
    check_wsr_generation,
    list_week_variants,
    register_generated_variant,
    resolve_variant_paths,
    sync_manifest_from_disk,
    variant_label,
)

_WSR_DUPLICATE_TEMPLATE = "WSR_ALREADY_GENERATED"


class WsrAlreadyGeneratedError(ValueError):
    """Raised when the same week was already generated with the same template."""

    def __init__(self, message: str, *, check: dict) -> None:
        super().__init__(message)
        self.check = check


def build_ppt_deck(
    content_json: Path,
    ppt_output: Path,
    *,
    template_path: Path,
) -> None:
    """Build a WSR deck with the template-agnostic engine (v2)."""
    from app.wsr_engine.main import WsrEngine

    ensure_output_dir()
    report = WsrEngine().run(
        template_path=template_path,
        content_path=content_json,
        output_path=ppt_output,
    )
    for line in report.summary_lines():
        print(f"   {line}")
    if report.errors:
        raise RuntimeError(f"WSR engine errors: {report.errors}")


def generate_wsr_deck(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    template_id: str,
    variant: int | None = None,
) -> dict:
    """
    Build ppt_content.json and the PowerPoint deck for a WSR week.
    Returns metadata, preview text, and output file paths.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must be on or before end_date ({end_date})."
        )

    generation_check = check_wsr_generation(start_date, end_date, template_id)
    if not generation_check["can_generate"]:
        raise WsrAlreadyGeneratedError(
            str(generation_check["message"]),
            check=generation_check,
        )

    resolved_variant = variant or int(generation_check["variant"])
    paths = resolve_variant_paths(start_date, end_date, resolved_variant)
    template_path = resolve_template_path(template_id)
    content = build_ppt_content(
        db,
        start_date=start_date,
        end_date=end_date,
    )

    ensure_output_dir()
    with paths.json_path.open("w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)

    preview_text = format_content_preview(content)
    paths.preview_path.write_text(preview_text, encoding="utf-8")

    build_ppt_deck(paths.json_path, paths.ppt_path, template_path=template_path)

    variant_record = register_generated_variant(
        start_date,
        end_date,
        variant=resolved_variant,
        template_id=template_id,
        ppt_path=paths.ppt_path,
    )

    cloud_upload = try_upload_wsr_ppt(
        paths.ppt_path,
        start_date=start_date,
        end_date=end_date,
    )

    preview_slides: list[dict] = []
    try:
        preview_slides = export_wsr_slide_previews(
            start_date=start_date,
            end_date=end_date,
            variant=resolved_variant,
            use_cache=False,
        )
    except Exception as exc:
        print(f"Warning: WSR slide preview export failed: {exc}")

    download_url = (
        f"/api/wsr/download?start_date={start_date.isoformat()}"
        f"&end_date={end_date.isoformat()}&variant={resolved_variant}"
    )
    return {
        "report_start_date": content["report_start_date"],
        "report_end_date": content["report_end_date"],
        "meta": content["meta"],
        "slides": content["slides"],
        "preview_slides": preview_slides,
        "preview": preview_text,
        "filename": paths.ppt_path.name,
        "json_filename": paths.json_path.name,
        "ppt_path": str(paths.ppt_path),
        "download_url": download_url,
        **cloud_response_fields_from_upload(cloud_upload),
        "variant": resolved_variant,
        "variant_label": variant_label(resolved_variant),
        "template_id": template_id,
        "template_name": variant_record.get("template_name"),
    }


def resolve_wsr_ppt_path(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
) -> Path:
    """Return the expected PPT path for a WSR week variant (may not exist yet)."""
    return resolve_variant_paths(start_date, end_date, variant).ppt_path


def _deck_slide_count(ppt_path: Path, preview_dir: Path) -> int:
    """Total slides in the generated WSR deck (not track count from content JSON)."""
    if ppt_path.is_file():
        try:
            from pptx import Presentation

            return len(Presentation(str(ppt_path)).slides)
        except Exception:
            pass
    if preview_dir.is_dir():
        preview_files = sorted(preview_dir.glob("slide_*.png"))
        if preview_files:
            return len(preview_files)
    return 0


def list_generated_wsr_weeks() -> list[dict]:
    """Scan output/ for generated WSR .pptx files, newest first."""
    if not OUTPUT_DIR.is_dir():
        return []

    seen_weeks: set[tuple[str, str]] = set()
    for ppt_path in OUTPUT_DIR.glob("WSR_*.pptx"):
        match = WSR_PPTX_RE.match(ppt_path.name)
        if not match:
            continue
        start_s, end_s = match.group(1), match.group(2)
        seen_weeks.add((start_s, end_s))

    weeks: list[dict] = []
    for start_s, end_s in seen_weeks:
        start_date = date.fromisoformat(start_s)
        end_date = date.fromisoformat(end_s)
        sync_manifest_from_disk(start_date, end_date)
        for variant_info in list_week_variants(start_date, end_date):
            variant = int(variant_info.get("variant") or 1)
            paths = resolve_variant_paths(start_date, end_date, variant)
            if not paths.ppt_path.is_file():
                continue

            preview_dir = wsr_preview_dir(start_date, end_date, variant=variant)
            slide_count = _deck_slide_count(paths.ppt_path, preview_dir)

            thumbnail_url: str | None = None
            if preview_dir.is_dir() and any(preview_dir.glob("slide_*.png")):
                thumbnail_url = (
                    f"/api/wsr/preview/image?start_date={start_s}"
                    f"&end_date={end_s}&slide_index=1&variant={variant}"
                )

            generated_at = variant_info.get("generated_at")
            if not generated_at:
                generated_at = datetime.fromtimestamp(
                    paths.ppt_path.stat().st_mtime
                ).isoformat()

            weeks.append(
                {
                    "report_start_date": start_s,
                    "report_end_date": end_s,
                    "variant": variant,
                    "variant_label": variant_label(variant),
                    "template_id": variant_info.get("template_id"),
                    "template_name": variant_info.get("template_name"),
                    "filename": paths.ppt_path.name,
                    "generated_at": generated_at,
                    "slide_count": slide_count,
                    "thumbnail_url": thumbnail_url,
                    "download_url": (
                        f"/api/wsr/download?start_date={start_s}&end_date={end_s}"
                        f"&variant={variant}"
                    ),
                }
            )

    weeks.sort(
        key=lambda item: (item["report_start_date"], -int(item["variant"])),
        reverse=True,
    )
    return weeks


def load_wsr_week(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
) -> dict:
    """Load an already-generated WSR week from disk (no regeneration)."""
    paths = resolve_variant_paths(start_date, end_date, variant)
    if not paths.ppt_path.is_file():
        raise FileNotFoundError(
            f"No WSR deck found for {start_date} to {end_date} "
            f"({variant_label(variant)}). Call POST /api/wsr/generate first."
        )

    variant_info = next(
        (
            item
            for item in list_week_variants(start_date, end_date)
            if int(item.get("variant") or 1) == variant
        ),
        None,
    )

    content: dict = {
        "report_start_date": start_date.isoformat(),
        "report_end_date": end_date.isoformat(),
        "slides": [],
        "meta": {
            "story_count": 0,
            "slide_count": 0,
            "titles_from_db": 0,
            "titles_fallback_summary": 0,
            "titles_generated": 0,
            "titles_reused": 0,
        },
    }
    if paths.json_path.is_file():
        with paths.json_path.open(encoding="utf-8") as f:
            content = json.load(f)

    preview_text = ""
    if paths.preview_path.is_file():
        preview_text = paths.preview_path.read_text(encoding="utf-8")

    preview_slides: list[dict] = []
    try:
        preview_slides = export_wsr_slide_previews(
            start_date=start_date,
            end_date=end_date,
            variant=variant,
            use_cache=True,
        )
    except Exception as exc:
        print(f"Warning: WSR slide preview load failed: {exc}")

    download_url = (
        f"/api/wsr/download?start_date={start_date.isoformat()}"
        f"&end_date={end_date.isoformat()}&variant={variant}"
    )
    return {
        "report_start_date": content["report_start_date"],
        "report_end_date": content["report_end_date"],
        "meta": content["meta"],
        "slides": content.get("slides", []),
        "preview_slides": preview_slides,
        "preview": preview_text,
        "filename": paths.ppt_path.name,
        "download_url": download_url,
        **cloud_response_fields(start_date, end_date),
        "variant": variant,
        "variant_label": variant_label(variant),
        "template_id": variant_info.get("template_id") if variant_info else None,
        "template_name": variant_info.get("template_name") if variant_info else None,
    }
