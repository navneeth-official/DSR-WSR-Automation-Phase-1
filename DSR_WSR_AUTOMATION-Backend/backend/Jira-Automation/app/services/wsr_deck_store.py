"""Publish / hydrate generated WSR decks and their sidecar files via SharePoint.

* The ``.pptx`` deck lives in ``SHAREPOINT_UPLOAD_FOLDER`` (default ``Shared Documents/WSR``).
* Sidecars (content JSON, preview text, week manifest) live in the ``_data`` sub-folder.
* The local work dir only caches these files; ``ensure_local_deck`` downloads a deck again
  whenever the cache was cleaned (restart purge, new VM, …).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from app.paths import wsr_manifest_path, wsr_output_paths
from app.services import sharepoint_storage as storage

logger = logging.getLogger(__name__)

WSR_PPTX_RE = re.compile(
    r"^WSR_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})(?:_v(\d+))?\.pptx$"
)


def deck_filename(start_date: date, end_date: date, variant: int = 1) -> str:
    return wsr_output_paths(start_date, end_date, variant=variant).ppt_path.name


# ── Remote queries ────────────────────────────────────────────────────────────

def remote_deck_items(*, use_cache: bool = True) -> dict[str, dict[str, Any]]:
    """``{filename: item}`` for every WSR deck in the SharePoint decks folder."""
    items = storage.list_folder(storage.decks_folder(), use_cache=use_cache)
    return {
        str(item["name"]): item
        for item in items
        if item.get("name") and WSR_PPTX_RE.match(str(item["name"]))
    }


def remote_deck_item(
    start_date: date, end_date: date, variant: int = 1, *, use_cache: bool = True
) -> dict[str, Any] | None:
    return remote_deck_items(use_cache=use_cache).get(
        deck_filename(start_date, end_date, variant)
    )


# ── Deck hydrate / publish ────────────────────────────────────────────────────

def ensure_local_deck(
    start_date: date, end_date: date, variant: int = 1, *, refresh: bool = False
) -> Path:
    """Return the cached deck path, downloading it from SharePoint when missing.

    Raises FileNotFoundError when the deck is not in SharePoint either.
    """
    path = wsr_output_paths(start_date, end_date, variant=variant).ppt_path
    if path.is_file() and not refresh:
        return path
    storage.require_storage()
    downloaded = storage.download_file(storage.decks_folder(), path.name, path)
    if downloaded is None:
        raise FileNotFoundError(
            f"No WSR deck found for {start_date} to {end_date} (variant {variant}): "
            f"{path.name} is not in SharePoint folder '{storage.decks_folder()}'."
        )
    return path


def publish_deck_file(start_date: date, end_date: date, variant: int = 1) -> dict[str, Any]:
    """Upload only the ``.pptx`` (used after editor changes). Raises on failure."""
    path = wsr_output_paths(start_date, end_date, variant=variant).ppt_path
    return storage.upload_file(path, storage.decks_folder())


def publish_deck(start_date: date, end_date: date, variant: int = 1) -> dict[str, Any]:
    """Upload the deck and its sidecars. The deck upload is mandatory; returns its item."""
    storage.require_storage()
    paths = wsr_output_paths(start_date, end_date, variant=variant)
    item = storage.upload_file(paths.ppt_path, storage.decks_folder())
    for sidecar in (paths.json_path, paths.preview_path):
        if sidecar.is_file():
            storage.upload_file(sidecar, storage.data_folder())
    return item


def restore_companions(start_date: date, end_date: date, variant: int = 1) -> None:
    """Best effort: re-download the content JSON / preview text when missing locally."""
    paths = wsr_output_paths(start_date, end_date, variant=variant)
    for sidecar in (paths.json_path, paths.preview_path):
        if sidecar.is_file():
            continue
        try:
            storage.download_file(storage.data_folder(), sidecar.name, sidecar)
        except Exception as exc:  # noqa: BLE001 - sidecars are optional for viewing
            logger.warning("Could not restore %s from SharePoint: %s", sidecar.name, exc)


# ── Manifest ──────────────────────────────────────────────────────────────────

def publish_manifest(start_date: date, end_date: date) -> None:
    path = wsr_manifest_path(start_date, end_date)
    if path.is_file():
        storage.upload_file(path, storage.data_folder())


def restore_manifest(start_date: date, end_date: date) -> bool:
    path = wsr_manifest_path(start_date, end_date)
    return storage.download_file(storage.data_folder(), path.name, path) is not None


# ── API response helpers ──────────────────────────────────────────────────────

def cloud_fields(item: dict[str, Any] | None) -> dict[str, Any]:
    """The cloud link fields every WSR API response carries."""
    url = (item or {}).get("webUrl")
    return {
        "cloud_web_url": url,
        "cloud_provider": "sharepoint" if url else None,
        "onedrive_web_url": None,
        "sharepoint_web_url": url,
    }
