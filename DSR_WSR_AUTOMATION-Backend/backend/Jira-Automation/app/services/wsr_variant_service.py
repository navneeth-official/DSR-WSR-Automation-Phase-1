"""Track multiple WSR deck variants (templates) per report week."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.paths import OUTPUT_DIR, wsr_manifest_path, wsr_output_paths
from app.services.wsr_template_upload_service import get_template_info

_WSR_PPTX_RE = re.compile(
    r"^WSR_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})(?:_v(\d+))?\.pptx$"
)
WSR_PPTX_RE = _WSR_PPTX_RE


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


def _load_manifest(start_date: date, end_date: date) -> dict[str, Any]:
    path = wsr_manifest_path(start_date, end_date)
    if not path.is_file():
        return {
            "report_start_date": start_date.isoformat(),
            "report_end_date": end_date.isoformat(),
            "variants": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "report_start_date": start_date.isoformat(),
            "report_end_date": end_date.isoformat(),
            "variants": [],
        }
    data.setdefault("variants", [])
    return data


def _save_manifest(start_date: date, end_date: date, manifest: dict[str, Any]) -> None:
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


def sync_manifest_from_disk(start_date: date, end_date: date) -> dict[str, Any]:
    """Ensure manifest reflects on-disk .pptx files (including legacy v1 decks)."""
    manifest = _load_manifest(start_date, end_date)
    known_filenames = {v.get("filename") for v in manifest["variants"]}

    start_s = start_date.isoformat()
    end_s = end_date.isoformat()
    for ppt_path in sorted(OUTPUT_DIR.glob(f"WSR_{start_s}_{end_s}*.pptx")):
        match = _WSR_PPTX_RE.match(ppt_path.name)
        if not match or match.group(1) != start_s or match.group(2) != end_s:
            continue
        if ppt_path.name in known_filenames:
            continue
        variant = int(match.group(3) or "1")
        manifest["variants"].append(
            _variant_from_ppt(start_date, end_date, ppt_path, variant=variant)
        )
        known_filenames.add(ppt_path.name)

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
) -> dict[str, Any]:
    manifest = sync_manifest_from_disk(start_date, end_date)
    record = _variant_from_ppt(
        start_date,
        end_date,
        ppt_path,
        variant=variant,
        template_id=template_id,
        template_name=_template_display_name(template_id),
    )
    manifest["variants"] = [
        v for v in manifest["variants"] if int(v.get("variant") or 1) != variant
    ]
    manifest["variants"].append(record)
    manifest["variants"] = sorted(
        manifest["variants"],
        key=lambda item: int(item.get("variant") or 1),
    )
    _save_manifest(start_date, end_date, manifest)
    return record


def resolve_variant_paths(start_date: date, end_date: date, variant: int = 1):
    return wsr_output_paths(start_date, end_date, variant=variant)
