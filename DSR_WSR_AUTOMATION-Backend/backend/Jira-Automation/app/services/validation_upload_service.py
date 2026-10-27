"""Upload validation artefacts (report JSON + annotated PNGs) to SharePoint.

Local files stay the primary source (``local-first``). The SharePoint copy is a
durable backup: if an annotation file is missing on disk (e.g. the VM output
folder was cleaned) it is downloaded again from SharePoint using the item/drive
ids stored in ``WSR_*_validation_meta.json``.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.config import get_settings
from app.paths import (
    wsr_stem,
    wsr_validation_dir,
    wsr_validation_meta_path,
    wsr_validation_report_path,
)
from app.services.cloud_upload_service import resolve_cloud_provider
from app.services.sharepoint_upload_service import (
    GRAPH_ROOT,
    _build_sharepoint_upload_url,
    get_sharepoint_access_token,
)

logger = logging.getLogger(__name__)


def _put_file(path: Path, *, folder: str, filename: str, mime: str, token: str) -> dict[str, Any]:
    url = _build_sharepoint_upload_url(folder, filename)
    with path.open("rb") as handle:
        response = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": mime},
            data=handle,
            timeout=120,
        )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"SharePoint upload failed ({response.status_code}): {response.text[:300]}")
    payload = response.json()
    return {
        "web_url": payload.get("webUrl"),
        "item_id": payload.get("id"),
        "drive_id": (payload.get("parentReference") or {}).get("driveId"),
    }


def load_validation_meta(start_date: date, end_date: date, *, variant: int = 1) -> dict[str, Any] | None:
    path = wsr_validation_meta_path(start_date, end_date, variant=variant)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def try_upload_validation_artifacts(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
) -> dict[str, Any] | None:
    """Upload report + annotated PNGs when SharePoint is the active provider."""
    if resolve_cloud_provider() != "sharepoint":
        return None

    report_path = wsr_validation_report_path(start_date, end_date, variant=variant)
    if not report_path.is_file():
        return None

    settings = get_settings()
    base_folder = (settings.sharepoint_upload_folder or "").strip() or "Shared Documents/WSR"
    folder = f"{base_folder.strip('/')}/{wsr_stem(start_date, end_date, variant=variant)}_validation"
    token = get_sharepoint_access_token()

    meta: dict[str, Any] = {
        "provider": "sharepoint",
        "folder": folder,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "report": _put_file(
            report_path,
            folder=folder,
            filename=report_path.name,
            mime="application/json",
            token=token,
        ),
        "images": {},
    }

    image_dir = wsr_validation_dir(start_date, end_date, variant=variant)
    if image_dir.is_dir():
        for image in sorted(image_dir.glob("slide_*_*.png")):
            try:
                meta["images"][image.name] = _put_file(
                    image, folder=folder, filename=image.name, mime="image/png", token=token
                )
            except Exception as exc:  # noqa: BLE001 - keep uploading the rest
                logger.warning("Could not upload %s: %s", image.name, exc)

    wsr_validation_meta_path(start_date, end_date, variant=variant).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


def _download_item(entry: dict[str, Any], destination: Path) -> bool:
    drive_id, item_id = entry.get("drive_id"), entry.get("item_id")
    if not drive_id or not item_id:
        return False
    token = get_sharepoint_access_token()
    response = requests.get(
        f"{GRAPH_ROOT}/drives/{drive_id}/items/{item_id}/content",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if response.status_code != 200:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.content)
    return True


def restore_validation_report(start_date: date, end_date: date, *, variant: int = 1) -> bool:
    """Re-download the report JSON from SharePoint when it is missing locally."""
    meta = load_validation_meta(start_date, end_date, variant=variant)
    if not meta or not meta.get("report"):
        return False
    try:
        return _download_item(
            meta["report"], wsr_validation_report_path(start_date, end_date, variant=variant)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not restore validation report: %s", exc)
        return False


def restore_validation_image(
    start_date: date,
    end_date: date,
    filename: str,
    *,
    variant: int = 1,
) -> Path | None:
    """Re-download one annotated PNG from SharePoint when it is missing locally."""
    meta = load_validation_meta(start_date, end_date, variant=variant)
    entry = ((meta or {}).get("images") or {}).get(filename)
    if not entry:
        return None
    destination = wsr_validation_dir(start_date, end_date, variant=variant) / filename
    try:
        return destination if _download_item(entry, destination) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not restore %s: %s", filename, exc)
        return None
