"""Unified cloud upload dispatcher for WSR decks (Google Drive, OneDrive, or SharePoint)."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Literal

from app.config import get_settings
from app.paths import wsr_cloud_meta_path
from app.services.google_drive_upload_service import (
    load_google_drive_web_url,
    save_google_drive_web_url,
    upload_ppt_to_google_drive,
)
from app.services.onedrive_upload_service import (
    load_onedrive_web_url,
    save_onedrive_web_url,
    upload_ppt_to_onedrive,
)
from app.services.sharepoint_upload_service import (
    load_sharepoint_web_url,
    save_sharepoint_item_meta,
    upload_ppt_to_sharepoint,
)

logger = logging.getLogger(__name__)

CloudProvider = Literal["google_drive", "onedrive", "sharepoint"]


def resolve_cloud_provider() -> CloudProvider | None:
    """Return active cloud upload provider from env, or None when disabled."""
    settings = get_settings()
    explicit = (settings.cloud_upload_provider or "").strip().lower()
    if explicit in ("google_drive", "googledrive", "google"):
        return "google_drive"
    if explicit in ("onedrive", "microsoft", "azure"):
        return "onedrive"
    if explicit in ("sharepoint", "sp"):
        return "sharepoint"
    if explicit in ("none", "off", "disabled"):
        return None

    if settings.sharepoint_upload_enabled:
        return "sharepoint"
    if settings.google_drive_upload_enabled:
        return "google_drive"
    if settings.onedrive_upload_enabled:
        return "onedrive"
    return None


def cloud_meta_path(start_date: date, end_date: date, *, variant: int = 1) -> Path:
    # Variant 1 keeps the legacy week-level file name (WSR_<start>_<end>_cloud.json).
    return wsr_cloud_meta_path(start_date, end_date, variant=variant)


def save_cloud_meta(
    start_date: date,
    end_date: date,
    *,
    web_url: str,
    provider: CloudProvider,
    variant: int = 1,
) -> None:
    path = cloud_meta_path(start_date, end_date, variant=variant)
    path.write_text(
        json.dumps({"webUrl": web_url, "provider": provider}, indent=2),
        encoding="utf-8",
    )


def load_cloud_meta(start_date: date, end_date: date, *, variant: int = 1) -> dict | None:
    path = cloud_meta_path(start_date, end_date, variant=variant)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("webUrl"):
                return {
                    "web_url": str(data["webUrl"]),
                    "provider": data.get("provider"),
                }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    sharepoint_url = load_sharepoint_web_url(start_date, end_date, variant=variant)
    if sharepoint_url:
        return {"web_url": sharepoint_url, "provider": "sharepoint"}

    google_url = load_google_drive_web_url(start_date, end_date)
    if google_url:
        return {"web_url": google_url, "provider": "google_drive"}

    onedrive_url = load_onedrive_web_url(start_date, end_date)
    if onedrive_url:
        return {"web_url": onedrive_url, "provider": "onedrive"}

    return None


def try_upload_wsr_ppt(
    ppt_path: Path,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    interactive: bool = False,
    variant: int = 1,
) -> dict | None:
    """
    Upload WSR deck using the configured cloud provider.

    Returns ``{"web_url": str, "provider": "google_drive"|"onedrive"|"sharepoint"}`` or None.
    SharePoint uses app-only auth (client secret) — the ``interactive`` flag is ignored.
    """
    provider = resolve_cloud_provider()
    if not provider:
        return None

    web_url: str | None = None
    try:
        if provider == "google_drive":
            web_url = upload_ppt_to_google_drive(
                ppt_path,
                interactive=interactive,
            )
            if start_date is not None and end_date is not None:
                save_google_drive_web_url(start_date, end_date, web_url)
        elif provider == "onedrive":
            web_url = upload_ppt_to_onedrive(
                ppt_path,
                interactive=interactive,
            )
            if start_date is not None and end_date is not None:
                save_onedrive_web_url(start_date, end_date, web_url)
        elif provider == "sharepoint":
            # App-only auth — no interactive flag needed
            item = upload_ppt_to_sharepoint(ppt_path)
            web_url = str(item["webUrl"])
            if start_date is not None and end_date is not None:
                save_sharepoint_item_meta(start_date, end_date, item, variant=variant)
    except Exception as exc:
        logger.warning("%s upload failed: %s", provider, exc)
        print(f"Warning: {provider} upload failed: {exc}")
        return None

    if start_date is not None and end_date is not None:
        save_cloud_meta(
            start_date, end_date, web_url=web_url, provider=provider, variant=variant
        )

    return {"web_url": web_url, "provider": provider}


def cloud_response_fields(start_date: date, end_date: date, *, variant: int = 1) -> dict:
    """Build API dict fields for cloud upload link (load from disk if present)."""
    meta = load_cloud_meta(start_date, end_date, variant=variant)
    if not meta:
        return {
            "cloud_web_url": None,
            "cloud_provider": None,
            "onedrive_web_url": None,
            "sharepoint_web_url": None,
        }
    provider = meta.get("provider")
    web_url = meta["web_url"]
    return {
        "cloud_web_url": web_url,
        "cloud_provider": provider,
        "onedrive_web_url": web_url if provider == "onedrive" else load_onedrive_web_url(start_date, end_date),
        "sharepoint_web_url": (
            web_url
            if provider == "sharepoint"
            else load_sharepoint_web_url(start_date, end_date, variant=variant)
        ),
    }


def cloud_response_fields_from_upload(result: dict | None) -> dict:
    """Build API dict fields immediately after an upload attempt."""
    if not result:
        return {
            "cloud_web_url": None,
            "cloud_provider": None,
            "onedrive_web_url": None,
            "sharepoint_web_url": None,
        }
    provider = result.get("provider")
    web_url = result.get("web_url")
    return {
        "cloud_web_url": web_url,
        "cloud_provider": provider,
        "onedrive_web_url": web_url if provider == "onedrive" else None,
        "sharepoint_web_url": web_url if provider == "sharepoint" else None,
    }
