"""Track multiple WSR deck variants (templates) per report week.

The decks themselves live in SharePoint; the per-week manifest (which template produced
which variant) is cached locally and mirrored to the SharePoint ``_data`` folder.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.paths import OUTPUT_DIR, wsr_manifest_path, wsr_output_paths
from app.services import wsr_deck_store as deck_store
from app.services.wsr_deck_store import WSR_PPTX_RE
from app.services.wsr_template_upload_service import get_template_info

logger = logging.getLogger(__name__)

_WSR_PPTX_RE = WSR_PPTX_RE


def variant_label(variant: int) -> str:
    if variant <= 1:
        return "WSR"
    return f"V{variant} WSR"


def _template_display_name(template_id: str | None) -> str:
    if not template_id:
        return "Unknown template"
    info = get_template_info(template_id)
    if info is None:
        return template_id
    return str(info.get("original_filename") or info.get("filename") or template_id)


def _empty_manifest(start_date: date, end_date: date) -> dict[str, Any]:
    return {
        "report_start_date": start_date.isoformat(),
        "report_end_date": end_date.isoformat(),
        "variants": [],
    }


def _load_manifest(start_date: date, end_date: date) -> dict[str, Any]:
    path = wsr_manifest_path(start_date, end_date)
    if not path.is_file():
        try:
            deck_store.restore_manifest(start_date, end_date)
        except Exception as exc:  # noqa: BLE001 - rebuilt from the deck listing below
            logger.warning("Could not restore manifest from SharePoint: %s", exc)
    if not path.is_file():
        return _empty_manifest(start_date, end_date)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_manifest(start_date, end_date)
    if not isinstance(data, dict):
        return _empty_manifest(start_date, end_date)
    data.setdefault("variants", [])
    return data


def _save_manifest(start_date: date, end_date: date, manifest: dict[str, Any]) -> None:
    """Write the local cache copy (SharePoint is updated by ``register_generated_variant``)."""
    path = wsr_manifest_path(start_date, end_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _variant_from_ppt(
    start_date: date,
    end_date: date,
    ppt_path: Path,
    *,
    variant: int,
    template_id: str | None = None,
    template_name: str | None = None,
) -> dict[str, Any]:
    modified = datetime.fromtimestamp(ppt_path.stat().st_mtime, tz=timezone.utc)
    return {
        "variant": variant,
        "template_id": template_id,
        "template_name": template_name or _template_display_name(template_id),
        "filename": ppt_path.name,
        "generated_at": modified.isoformat(),
    }


def _variant_from_remote_item(item: dict[str, Any], *, variant: int) -> dict[str, Any]:
    return {
        "variant": variant,
        "template_id": None,
        "template_name": _template_display_name(None),
        "filename": item.get("name"),
        "generated_at": item.get("lastModifiedDateTime")
        or datetime.now(timezone.utc).isoformat(),
    }


def sync_manifest_from_disk(start_date: date, end_date: date) -> dict[str, Any]:
    """Make the manifest reflect the decks that exist in SharePoint for this week.

    Decks missing from the manifest (e.g. uploaded manually) are added; manifest entries
    whose deck was deleted from SharePoint are dropped.
    """
    manifest = _load_manifest(start_date, end_date)

    start_s = start_date.isoformat()
    end_s = end_date.isoformat()
    remote = {
        name: item
        for name, item in deck_store.remote_deck_items().items()
        if (m := _WSR_PPTX_RE.match(name)) and m.group(1) == start_s and m.group(2) == end_s
    }

    manifest["variants"] = [v for v in manifest["variants"] if v.get("filename") in remote]
    known_filenames = {v.get("filename") for v in manifest["variants"]}

    for name in sorted(remote):
        if name in known_filenames:
            continue
        variant = int(_WSR_PPTX_RE.match(name).group(3) or "1")  # type: ignore[union-attr]
        local = OUTPUT_DIR / name
        if local.is_file():
            record = _variant_from_ppt(start_date, end_date, local, variant=variant)
        else:
            record = _variant_from_remote_item(remote[name], variant=variant)
        manifest["variants"].append(record)
        known_filenames.add(name)

    manifest["variants"] = sorted(
        manifest["variants"],
        key=lambda item: int(item.get("variant") or 1),
    )
    _save_manifest(start_date, end_date, manifest)
    return manifest


def list_week_variants(start_date: date, end_date: date) -> list[dict[str, Any]]:
    manifest = sync_manifest_from_disk(start_date, end_date)
    return [v for v in manifest["variants"] if v.get("filename")]


def find_variant_by_template(
    start_date: date,
    end_date: date,
    template_id: str,
) -> dict[str, Any] | None:
    for item in list_week_variants(start_date, end_date):
        if item.get("template_id") == template_id:
            return item
    return None


def next_variant_number(start_date: date, end_date: date) -> int:
    variants = list_week_variants(start_date, end_date)
    if not variants:
        return 1
    return max(int(v.get("variant") or 1) for v in variants) + 1


def check_wsr_generation(
    start_date: date,
    end_date: date,
    template_id: str,
) -> dict[str, Any]:
    """
    Decide whether a new generation is allowed.

    - Same week + same template → block with message to View WSR.
    - Same week + different template → allow as next variant (typically V2).
    - New week → allow as variant 1.
    """
    existing_same = find_variant_by_template(start_date, end_date, template_id)
    if existing_same is not None:
        variant = int(existing_same.get("variant") or 1)
        return {
            "can_generate": False,
            "reason": "same_template",
            "variant": variant,
            "variant_label": variant_label(variant),
            "template_id": template_id,
            "template_name": existing_same.get("template_name"),
            "message": (
                f"A WSR for {start_date.isoformat()} to {end_date.isoformat()} was "
                f"already generated with this template. Open View WSR to review it."
            ),
        }

    variants = list_week_variants(start_date, end_date)
    next_variant = next_variant_number(start_date, end_date)
    if variants:
        return {
            "can_generate": True,
            "reason": "different_template",
            "variant": next_variant,
            "variant_label": variant_label(next_variant),
            "existing_variants": [
                {
                    "variant": int(v.get("variant") or 1),
                    "variant_label": variant_label(int(v.get("variant") or 1)),
                    "template_id": v.get("template_id"),
                    "template_name": v.get("template_name"),
                }
                for v in variants
            ],
            "message": (
                f"This week already has a generated WSR. The new deck will be saved as "
                f"{variant_label(next_variant)}."
            ),
        }

    return {
        "can_generate": True,
        "reason": "new_week",
        "variant": 1,
        "variant_label": variant_label(1),
        "message": "No WSR exists for this week yet.",
    }


def register_generated_variant(
    start_date: date,
    end_date: date,
    *,
    variant: int,
    template_id: str,
    ppt_path: Path,
    slide_count: int | None = None,
) -> dict[str, Any]:
    """Record a freshly generated (and already published) deck in the week manifest."""
    manifest = sync_manifest_from_disk(start_date, end_date)
    record = _variant_from_ppt(
        start_date,
        end_date,
        ppt_path,
        variant=variant,
        template_id=template_id,
        template_name=_template_display_name(template_id),
    )
    if slide_count:
        record["slide_count"] = int(slide_count)
    manifest["variants"] = [
        v for v in manifest["variants"] if int(v.get("variant") or 1) != variant
    ]
    manifest["variants"].append(record)
    manifest["variants"] = sorted(
        manifest["variants"],
        key=lambda item: int(item.get("variant") or 1),
    )
    _save_manifest(start_date, end_date, manifest)
    deck_store.publish_manifest(start_date, end_date)
    return record


def resolve_variant_paths(start_date: date, end_date: date, variant: int = 1):
    return wsr_output_paths(start_date, end_date, variant=variant)
