"""Store, list, preview, and resolve WSR templates.

Saved templates live ONLY in SharePoint (``SHAREPOINT_TEMPLATE_FOLDER``, default
``Shared Documents/WSR Template``) under the **uploaded file's own name**
(``My Template.pptx`` + ``My Template.json``; a repeat name becomes ``My Template (2).pptx``).

The template id used by the API is derived from that name (``My_Template``), so an id can
always be mapped back to its SharePoint file by listing the folder. The local
``wsr_templates`` directory is a disposable cache (``<id>.pptx`` + ``<id>.json``) that is
re-hydrated on demand. The staged *draft* (upload preview before "Save") only ever
exists in the local work dir.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.paths import (
    WSR_TEMPLATE_DRAFT_META,
    WSR_TEMPLATE_DRAFT_PPT,
    WSR_TEMPLATES_DIR,
    ensure_output_dir,
    wsr_template_draft_preview_dir,
    wsr_template_meta_path,
    wsr_template_ppt_path,
    wsr_template_preview_dir,
)
from app.services import sharepoint_storage as storage
from app.services.ppt_slide_images import export_all_slides_to_png, list_all_slide_indices
from app.utils.safe_fs import prepare_preview_directory, remove_directory

logger = logging.getLogger(__name__)

DRAFT_TEMPLATE_ID = "__draft__"
_TEMPLATE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
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


def template_id_from_stem(stem: str) -> str:
    """API template id for a SharePoint file stem (``My Template (2)`` -> ``My_Template_2``)."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")
    return slug[:80] or "template"


def safe_remote_stem(original_filename: str) -> str:
    """The uploaded file's name without extension, cleaned for SharePoint."""
    name = re.split(r"[\\/]", original_filename)[-1]
    stem = name[: -len(".pptx")] if name.lower().endswith(".pptx") else Path(name).stem
    stem = re.sub(r'[\\/:*?"<>|#%~&{}]+', "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" ._")
    return stem[:100].rstrip(" ._") or "template"


def _remote_template_stems(*, use_cache: bool = True) -> dict[str, str]:
    """``{template id: SharePoint file stem}`` for every template in the folder."""
    stems: dict[str, str] = {}
    for item in storage.list_folder(storage.templates_folder(), use_cache=use_cache):
        name = str(item.get("name") or "")
        if name.lower().endswith(".pptx"):
            stem = name[: -len(".pptx")]
            stems.setdefault(template_id_from_stem(stem), stem)
    return stems


def claim_template_identity(original_filename: str) -> tuple[str, str]:
    """Pick ``(template_id, sharepoint_stem)`` for a new upload.

    The stem is the uploaded file's name; if that name (or its id) is already used by
    another template, `` (2)``, `` (3)`` … is appended so nothing is overwritten.
    """
    base = safe_remote_stem(original_filename)
    remote = _remote_template_stems(use_cache=False)
    taken_ids = set(remote)
    if WSR_TEMPLATES_DIR.is_dir():
        taken_ids |= {path.stem for path in WSR_TEMPLATES_DIR.glob("*.pptx")}
    taken_stems = {stem.lower() for stem in remote.values()}

    stem, counter = base, 1
    while stem.lower() in taken_stems or template_id_from_stem(stem) in taken_ids:
        counter += 1
        stem = f"{base} ({counter})"
    return template_id_from_stem(stem), stem


def _hydrate_template(template_id: str) -> bool:
    """Make sure ``<id>.pptx`` (+ ``<id>.json``) are cached locally.

    Returns False when the template does not exist (in SharePoint, for saved templates).
    """
    if template_id == DRAFT_TEMPLATE_ID:
        return WSR_TEMPLATE_DRAFT_PPT.is_file()
    if not _TEMPLATE_ID_RE.match(template_id):
        return False

    ppt_path = wsr_template_ppt_path(template_id)
    if ppt_path.is_file():
        return True

    storage.require_storage()
    stem = _remote_template_stems().get(template_id)
    if stem is None:
        return False

    _ensure_templates_dir()
    folder = storage.templates_folder()
    if storage.download_file(folder, f"{stem}.pptx", ppt_path) is None:
        return False

    meta_path = wsr_template_meta_path(template_id)
    if not meta_path.is_file():
        try:
            storage.download_file(folder, f"{stem}.json", meta_path)
        except Exception as exc:  # noqa: BLE001 - metadata is optional
            logger.warning("Could not restore template metadata %s.json: %s", stem, exc)
    return True


def _publish_template(template_id: str, remote_stem: str) -> None:
    """Upload the cached template to SharePoint as ``<remote_stem>.pptx`` + ``.json``.

    On failure the local copies are removed too, so nothing is left outside SharePoint.
    """
    ppt_path = wsr_template_ppt_path(template_id)
    meta_path = wsr_template_meta_path(template_id)
    folder = storage.templates_folder()
    try:
        storage.upload_file(ppt_path, folder, f"{remote_stem}.pptx")
        storage.upload_file(meta_path, folder, f"{remote_stem}.json")
    except Exception:
        ppt_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        raise


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
    """Templates in the SharePoint template folder, newest first."""
    storage.require_storage()
    _ensure_templates_dir()

    templates: list[dict] = []
    for item in storage.list_folder(storage.templates_folder()):
        name = str(item.get("name") or "")
        if not name.lower().endswith(".pptx"):
            continue
        template_id = template_id_from_stem(name[: -len(".pptx")])
        if any(t["id"] == template_id for t in templates):
            continue
        if not _hydrate_template(template_id):
            continue
        templates.append(
            _build_template_info(
                template_id=template_id,
                ppt_path=wsr_template_ppt_path(template_id),
                meta_path=wsr_template_meta_path(template_id),
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

    if not _hydrate_template(template_id):
        return None
    ppt_path = wsr_template_ppt_path(template_id)
    return _build_template_info(
        template_id=template_id,
        ppt_path=ppt_path,
        meta_path=wsr_template_meta_path(template_id),
    )


def resolve_template_path(template_id: str | None) -> Path:
    """Resolve a saved template id to its .pptx path."""
    if not template_id or template_id == DRAFT_TEMPLATE_ID:
        raise ValueError("A saved template must be selected for WSR generation.")

    if not _hydrate_template(template_id):
        raise FileNotFoundError(
            f"WSR template not found: {template_id} "
            f"(looked in SharePoint folder '{storage.templates_folder()}')"
        )
    return wsr_template_ppt_path(template_id)


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

    storage.require_storage()
    _ensure_templates_dir()
    draft_meta = _read_meta(WSR_TEMPLATE_DRAFT_META)
    original_filename = str(draft_meta.get("original_filename") or "template.pptx")
    template_id, remote_stem = claim_template_identity(original_filename)
    ppt_path = wsr_template_ppt_path(template_id)
    meta_path = wsr_template_meta_path(template_id)

    shutil.copy2(WSR_TEMPLATE_DRAFT_PPT, ppt_path)
    _write_meta(
        meta_path,
        {
            "original_filename": original_filename,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    _publish_template(template_id, remote_stem)

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

    storage.require_storage()
    _ensure_templates_dir()
    template_id, remote_stem = claim_template_identity(original_filename)
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
    _publish_template(template_id, remote_stem)

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

    if not _hydrate_template(resolved_id):
        return None
    ppt_path = _template_ppt_for_id(resolved_id)

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

    if not _hydrate_template(resolved_id):
        raise FileNotFoundError(f"WSR template not found: {resolved_id}")
    ppt_path = _template_ppt_for_id(resolved_id)

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
    if not image_path.is_file() and resolved_id != DRAFT_TEMPLATE_ID:
        # Cache was cleaned: pull the template from SharePoint and render it again.
        try:
            export_template_slide_previews(template_id=resolved_id, use_cache=True)
        except Exception as exc:  # noqa: BLE001 - reported as "not found" below
            logger.warning("Could not rebuild template previews for %s: %s", resolved_id, exc)
    if not image_path.is_file():
        raise FileNotFoundError(f"Template preview image not found: {image_path}")
    return image_path
