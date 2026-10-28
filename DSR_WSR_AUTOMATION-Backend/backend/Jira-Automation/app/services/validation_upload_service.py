"""Store validation artefacts (report JSON + annotated PNGs) in SharePoint.

Everything for one deck lives in ``<SharePoint data folder>/<deck stem>_validation/``
(default ``Shared Documents/WSR/_data/WSR_<start>_<end>[_vN]_validation/``). The local copy
is only a cache: when the report or an annotated image is missing locally it is downloaded
again from that folder, addressed purely by path (no id bookkeeping needed).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from app.paths import (
    wsr_stem,
    wsr_validation_dir,
    wsr_validation_report_path,
)
from app.services import sharepoint_storage as storage

logger = logging.getLogger(__name__)

_ANNOTATION_RE = re.compile(r"^slide_\d+_[a-z0-9._-]+\.png$")


def validation_remote_folder(start_date: date, end_date: date, *, variant: int = 1) -> str:
    return f"{storage.data_folder()}/{wsr_stem(start_date, end_date, variant=variant)}_validation"


def try_upload_validation_artifacts(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
) -> dict[str, Any] | None:
    """Upload the report + annotated PNGs. Returns a small summary, or None when skipped."""
    if not storage.storage_configured():
        return None

    report_path = wsr_validation_report_path(start_date, end_date, variant=variant)
    if not report_path.is_file():
        return None

    folder = validation_remote_folder(start_date, end_date, variant=variant)
    report_item = storage.upload_file(report_path, folder)

    uploaded_images = 0
    current: set[str] = set()
    image_dir = wsr_validation_dir(start_date, end_date, variant=variant)
    if image_dir.is_dir():
        for image in sorted(image_dir.glob("slide_*_*.png")):
            try:
                storage.upload_file(image, folder)
                uploaded_images += 1
                current.add(image.name)
            except Exception as exc:  # noqa: BLE001 - keep uploading the rest
                logger.warning("Could not upload %s: %s", image.name, exc)

    # Drop annotated images from a previous run that no longer apply.
    try:
        for item in storage.list_folder(folder, use_cache=False):
            name = str(item.get("name") or "")
            if _ANNOTATION_RE.match(name) and name not in current:
                storage.delete_file(folder, name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not clean stale annotated images: %s", exc)

    return {"folder": folder, "report": report_item, "images": uploaded_images}


def restore_validation_images(start_date: date, end_date: date, *, variant: int = 1) -> int:
    """Download every annotated PNG that is missing locally. Returns how many were fetched."""
    if not storage.storage_configured():
        return 0
    folder = validation_remote_folder(start_date, end_date, variant=variant)
    image_dir = wsr_validation_dir(start_date, end_date, variant=variant)
    restored = 0
    try:
        for item in storage.list_folder(folder, use_cache=False):
            name = str(item.get("name") or "")
            if not _ANNOTATION_RE.match(name) or (image_dir / name).is_file():
                continue
            if storage.download_file(folder, name, image_dir / name) is not None:
                restored += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not restore annotated images: %s", exc)
    return restored


def restore_validation_report(start_date: date, end_date: date, *, variant: int = 1) -> bool:
    """Re-download the report JSON (and annotated PNGs) from SharePoint when missing locally."""
    if not storage.storage_configured():
        return False
    report_path = wsr_validation_report_path(start_date, end_date, variant=variant)
    try:
        downloaded = storage.download_file(
            validation_remote_folder(start_date, end_date, variant=variant),
            report_path.name,
            report_path,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not restore validation report: %s", exc)
        return False
    if downloaded is None:
        return False
    restore_validation_images(start_date, end_date, variant=variant)
    return True


def restore_validation_image(
    start_date: date,
    end_date: date,
    filename: str,
    *,
    variant: int = 1,
) -> Path | None:
    """Re-download one annotated PNG from SharePoint when it is missing locally."""
    if not storage.storage_configured() or not _ANNOTATION_RE.match(filename):
        return None
    destination = wsr_validation_dir(start_date, end_date, variant=variant) / filename
    try:
        return storage.download_file(
            validation_remote_folder(start_date, end_date, variant=variant),
            filename,
            destination,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not restore %s: %s", filename, exc)
        return None
