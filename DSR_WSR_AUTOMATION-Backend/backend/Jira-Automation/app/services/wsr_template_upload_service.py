"""Store, list, preview, and resolve WSR templates under output/wsr_templates/."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.paths import (
    UPLOADED_WSR_TEMPLATE_META,
    UPLOADED_WSR_TEMPLATE_PPT,
    WSR_TEMPLATE_DRAFT_META,
    WSR_TEMPLATE_DRAFT_PPT,
    WSR_TEMPLATES_DIR,
    ensure_output_dir,
    uploaded_wsr_template_preview_dir,
    wsr_template_draft_preview_dir,
    wsr_template_meta_path,
    wsr_template_ppt_path,
    wsr_template_preview_dir,
)
from app.services.ppt_slide_images import export_all_slides_to_png, list_all_slide_indices
from app.utils.safe_fs import prepare_preview_directory, remove_directory

DRAFT_TEMPLATE_ID = "__draft__"
PPT_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


def _ppt_preview_version(ppt_path: Path) -> int:
    return int(ppt_path.stat().st_mtime)


def _slide_index_from_png(path: Path) -> int | None:
    match = re.match(r"slide_(\d+)\.png$", path.name, re.I)
    if not match:
        return None
    return int(match.group(1))


def _read_meta(meta_path: Path) -> dict:
    if not meta_path.is_file():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _write_meta(meta_path: Path, payload: dict) -> None:
    meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ensure_templates_dir() -> Path:
    ensure_output_dir()
    WSR_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    return WSR_TEMPLATES_DIR


def _migrate_legacy_uploaded_template() -> None:
    """Import the legacy single-slot upload into the template library once."""
    _ensure_templates_dir()
    if any(WSR_TEMPLATES_DIR.glob("*.pptx")):
        return
    if not UPLOADED_WSR_TEMPLATE_PPT.is_file():
        return

    template_id = uuid.uuid4().hex[:12]
    ppt_path = wsr_template_ppt_path(template_id)
    meta_path = wsr_template_meta_path(template_id)
    stat = UPLOADED_WSR_TEMPLATE_PPT.stat()
    original_filename = UPLOADED_WSR_TEMPLATE_PPT.name
    legacy_meta = _read_meta(UPLOADED_WSR_TEMPLATE_META)
    if legacy_meta.get("original_filename"):
        original_filename = str(legacy_meta["original_filename"])

    shutil.copy2(UPLOADED_WSR_TEMPLATE_PPT, ppt_path)
    _write_meta(
        meta_path,
        {
            "original_filename": original_filename,
            "saved_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        },
    )

    legacy_preview = uploaded_wsr_template_preview_dir()
    target_preview = wsr_template_preview_dir(template_id)
    if legacy_preview.is_dir():
        if target_preview.is_dir():
            remove_directory(target_preview)
        shutil.copytree(legacy_preview, target_preview)


def _template_ppt_for_id(template_id: str) -> Path:
    if template_id == DRAFT_TEMPLATE_ID:
        return WSR_TEMPLATE_DRAFT_PPT
    return wsr_template_ppt_path(template_id)


def _template_meta_for_id(template_id: str) -> Path:
    if template_id == DRAFT_TEMPLATE_ID:
        return WSR_TEMPLATE_DRAFT_META
    return wsr_template_meta_path(template_id)


def _template_preview_dir_for_id(template_id: str) -> Path:
    if template_id == DRAFT_TEMPLATE_ID:
        return wsr_template_draft_preview_dir()
    return wsr_template_preview_dir(template_id)


def build_template_preview_image_url(
    *,
    slide_index: int,
    template_id: str | None = None,
    version: int | None = None,
) -> str:
    url = f"/api/wsr/template/preview/image?slide_index={slide_index}"
    if template_id:
        url = f"{url}&template_id={template_id}"
    if version is not None:
        url = f"{url}&v={version}"
    return url


def build_template_thumbnail_url(*, template_id: str, version: int | None = None) -> str:
    url = (
        f"/api/wsr/template/preview/image?template_id={template_id}"
        f"&slide_index=1&thumb=1"
    )
    if version is not None:
        url = f"{url}&v={version}"
    return url


def _build_template_info(
    *,
    template_id: str,
    ppt_path: Path,
    meta_path: Path,
    is_draft: bool = False,
) -> dict:
    stat = ppt_path.stat()
    slides = list_all_slide_indices(ppt_path)
    meta = _read_meta(meta_path)
    original_filename = meta.get("original_filename") or ppt_path.name
    updated_at = meta.get("saved_at")
    if not updated_at:
        updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

    preview_version = _ppt_preview_version(ppt_path)
    return {
        "id": template_id,
        "filename": ppt_path.name,
        "original_filename": str(original_filename),
        "updated_at": updated_at,
        "slide_count": len(slides),
        "file_size_bytes": stat.st_size,
        "is_draft": is_draft,
        "thumbnail_url": build_template_thumbnail_url(
            template_id=template_id,
            version=preview_version,
        ),
    }


def list_saved_templates() -> list[dict]:
    _migrate_legacy_uploaded_template()
    _ensure_templates_dir()

    templates: list[dict] = []
    for ppt_path in WSR_TEMPLATES_DIR.glob("*.pptx"):
        template_id = ppt_path.stem
        meta_path = wsr_template_meta_path(template_id)
        templates.append(
            _build_template_info(
                template_id=template_id,
                ppt_path=ppt_path,
                meta_path=meta_path,
            )
        )

    templates.sort(
        key=lambda item: item["updated_at"],
        reverse=True,
    )
    return templates


def get_draft_template_info() -> dict | None:
    if not WSR_TEMPLATE_DRAFT_PPT.is_file():
        return None
    return _build_template_info(
        template_id=DRAFT_TEMPLATE_ID,
        ppt_path=WSR_TEMPLATE_DRAFT_PPT,
        meta_path=WSR_TEMPLATE_DRAFT_META,
        is_draft=True,
    )


def get_template_info(template_id: str) -> dict | None:
    if template_id == DRAFT_TEMPLATE_ID:
        return get_draft_template_info()

    ppt_path = wsr_template_ppt_path(template_id)
    if not ppt_path.is_file():
        return None
    return _build_template_info(
        template_id=template_id,
        ppt_path=ppt_path,
        meta_path=wsr_template_meta_path(template_id),
    )


def resolve_template_path(template_id: str | None) -> Path:
    """Resolve a saved template id to its .pptx path."""
    if not template_id or template_id == DRAFT_TEMPLATE_ID:
        raise ValueError("A saved template must be selected for WSR generation.")

    ppt_path = wsr_template_ppt_path(template_id)
    if not ppt_path.is_file():
        raise FileNotFoundError(f"WSR template not found: {template_id}")
    return ppt_path


def stage_template_upload(*, content: bytes, original_filename: str) -> dict:
    """Stage an uploaded .pptx for preview; user must save to add to library."""
    if not original_filename.lower().endswith(".pptx"):
        raise ValueError("Only .pptx files are supported.")

    ensure_output_dir()
    WSR_TEMPLATE_DRAFT_PPT.write_bytes(content)
    _write_meta(
        WSR_TEMPLATE_DRAFT_META,
        {
            "original_filename": Path(original_filename).name,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    preview_dir = wsr_template_draft_preview_dir()
    prepare_preview_directory(preview_dir)

    preview_slides = export_template_slide_previews(
        template_id=DRAFT_TEMPLATE_ID,
        use_cache=False,
    )
    info = get_draft_template_info()
    if info is None:
        raise RuntimeError("Template staging failed.")

    return {
        **info,
        "preview_slides": preview_slides,
    }


def save_draft_template() -> dict:
    """Persist the staged draft into the saved template library."""
    if not WSR_TEMPLATE_DRAFT_PPT.is_file():
        raise FileNotFoundError("No staged template to save.")

    _ensure_templates_dir()
    template_id = uuid.uuid4().hex[:12]
    ppt_path = wsr_template_ppt_path(template_id)
    meta_path = wsr_template_meta_path(template_id)

    shutil.copy2(WSR_TEMPLATE_DRAFT_PPT, ppt_path)
    draft_meta = _read_meta(WSR_TEMPLATE_DRAFT_META)
    _write_meta(
        meta_path,
        {
            "original_filename": draft_meta.get("original_filename") or ppt_path.name,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    draft_preview = wsr_template_draft_preview_dir()
    target_preview = wsr_template_preview_dir(template_id)
    if draft_preview.is_dir():
        if target_preview.is_dir():
            remove_directory(target_preview)
        shutil.copytree(draft_preview, target_preview)

    cancel_draft_template()
    info = get_template_info(template_id)
    if info is None:
        raise RuntimeError("Failed to save staged template.")
    return info


def cancel_draft_template() -> None:
    if WSR_TEMPLATE_DRAFT_PPT.is_file():
        WSR_TEMPLATE_DRAFT_PPT.unlink()
    if WSR_TEMPLATE_DRAFT_META.is_file():
        WSR_TEMPLATE_DRAFT_META.unlink()
    preview_dir = wsr_template_draft_preview_dir()
    if preview_dir.is_dir():
        try:
            remove_directory(preview_dir)
        except OSError:
            prepare_preview_directory(preview_dir)


def save_uploaded_template(*, content: bytes, original_filename: str) -> dict:
    """Persist uploaded .pptx directly to the template library (legacy upload page)."""
    if not original_filename.lower().endswith(".pptx"):
        raise ValueError("Only .pptx files are supported.")

    _ensure_templates_dir()
    template_id = uuid.uuid4().hex[:12]
    ppt_path = wsr_template_ppt_path(template_id)
    meta_path = wsr_template_meta_path(template_id)

    ppt_path.write_bytes(content)
    _write_meta(
        meta_path,
        {
            "original_filename": Path(original_filename).name,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    preview_dir = wsr_template_preview_dir(template_id)
    prepare_preview_directory(preview_dir)

    preview_slides = export_template_slide_previews(
        template_id=template_id,
        use_cache=False,
    )
    info = get_template_info(template_id)
    if info is None:
        raise RuntimeError("Template upload failed to persist.")

    return {
        **info,
        "filename": info["filename"],
        "original_filename": info["original_filename"],
        "uploaded_at": info["updated_at"],
        "preview_slides": preview_slides,
    }


def get_uploaded_template_info() -> dict | None:
    """Return metadata for the newest saved template (legacy single-template API)."""
    templates = list_saved_templates()
    if not templates:
        return None
    latest = templates[0]
    return {
        "filename": latest["filename"],
        "original_filename": latest["original_filename"],
        "uploaded_at": latest["updated_at"],
        "slide_count": latest["slide_count"],
        "file_size_bytes": latest["file_size_bytes"],
    }


def list_cached_template_slide_previews(
    *,
    template_id: str | None = None,
) -> list[dict] | None:
    templates = list_saved_templates()
    resolved_id = template_id or (templates[0]["id"] if templates else None)
    if not resolved_id:
        return None

    ppt_path = _template_ppt_for_id(resolved_id)
    if not ppt_path.is_file():
        return None

    preview_dir = _template_preview_dir_for_id(resolved_id)
    if not preview_dir.is_dir():
        return None

    png_files = sorted(preview_dir.glob("slide_*.png"))
    if not png_files:
        return None

    ppt_mtime = ppt_path.stat().st_mtime
    preview_version = _ppt_preview_version(ppt_path)
    # Windows filesystem timestamps can trail the .pptx write by 1–2 seconds.
    if any(path.stat().st_mtime + 2 < ppt_mtime for path in png_files):
        return None

    titles = {
        item["slide_index"]: item["title"]
        for item in list_all_slide_indices(ppt_path)
    }

    slides: list[dict] = []
    for path in png_files:
        slide_index = _slide_index_from_png(path)
        if slide_index is None:
            continue
        slides.append(
            {
                "slide_index": slide_index,
                "title": titles.get(slide_index) or f"Slide {slide_index}",
                "image_url": build_template_preview_image_url(
                    slide_index=slide_index,
                    template_id=resolved_id,
                    version=preview_version,
                ),
            }
        )

    return slides or None


def export_template_slide_previews(
    *,
    template_id: str | None = None,
    width_px: int = 1280,
    use_cache: bool = True,
) -> list[dict]:
    resolved_id = template_id
    if not resolved_id:
        templates = list_saved_templates()
        if not templates:
            raise FileNotFoundError("No saved WSR templates found.")
        resolved_id = templates[0]["id"]

    if use_cache:
        cached = list_cached_template_slide_previews(template_id=resolved_id)
        if cached is not None:
            return cached

    ppt_path = _template_ppt_for_id(resolved_id)
    if not ppt_path.is_file():
        raise FileNotFoundError(f"WSR template not found: {resolved_id}")

    preview_dir = _template_preview_dir_for_id(resolved_id)
    prepare_preview_directory(preview_dir)
    preview_version = _ppt_preview_version(ppt_path)

    exported = export_all_slides_to_png(
        ppt_path,
        preview_dir,
        width_px=width_px,
    )
    if not exported:
        slides = list_all_slide_indices(ppt_path)
        exported = [
            {
                "slide_index": s["slide_index"],
                "title": s["title"],
                "image_path": str(preview_dir / f"slide_{s['slide_index']:02d}.png"),
            }
            for s in slides
        ]

    return [
        {
            "slide_index": item["slide_index"],
            "title": item.get("title") or f"Slide {item['slide_index']}",
            "image_url": build_template_preview_image_url(
                slide_index=int(item["slide_index"]),
                template_id=resolved_id,
                version=preview_version,
            ),
        }
        for item in sorted(exported, key=lambda row: int(row["slide_index"]))
    ]


def resolve_template_preview_image_path(
    *,
    slide_index: int,
    template_id: str | None = None,
) -> Path:
    resolved_id = template_id
    if not resolved_id:
        templates = list_saved_templates()
        if not templates:
            raise FileNotFoundError("No saved WSR templates found.")
        resolved_id = templates[0]["id"]

    image_path = (
        _template_preview_dir_for_id(resolved_id) / f"slide_{slide_index:02d}.png"
    )
    if not image_path.is_file():
        raise FileNotFoundError(f"Template preview image not found: {image_path}")
    return image_path
