"""SharePoint document-library storage — the only durable store for WSR files.

Everything the app persists (WSR templates, generated decks, content JSON, manifests,
validation reports and annotated images) is read from / written to SharePoint through
this module. The local work directory (``app.paths.OUTPUT_DIR``) is a disposable cache.

Folder layout (all configurable, see ``app/config.py``)::

    Shared Documents/WSR Template/   <id>.pptx + <id>.json        (templates)
    Shared Documents/WSR/            WSR_<start>_<end>[_vN].pptx   (decks)
    Shared Documents/WSR/_data/      content JSON, preview text, manifest,
                                     <stem>_validation/ report + annotated PNGs

SharePoint is mandatory: when it is not configured every call raises
``StorageNotConfiguredError`` (surfaced by the API as HTTP 503) instead of silently
falling back to local disk.

Callers must use ``from app.services import sharepoint_storage as storage`` and call
``storage.<function>()`` so tests can swap the functions for an in-memory fake.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

from app.config import get_settings
from app.services import sharepoint_upload_service as sp

logger = logging.getLogger(__name__)

LISTING_TTL_SECONDS = 30.0
TOKEN_TTL_SECONDS = 45 * 60
_RETRY_STATUSES = (429, 502, 503, 504)

_MIME_BY_SUFFIX = {
    ".pptx": sp.PPT_MIME,
    ".json": "application/json",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".png": "image/png",
}


class StorageError(RuntimeError):
    """SharePoint could not be reached or rejected a request."""


class StorageNotConfiguredError(StorageError):
    """SharePoint credentials / site are not configured."""


# ── Configuration ─────────────────────────────────────────────────────────────

def storage_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.azure_client_id.strip()
        and settings.azure_client_secret.strip()
        and (settings.azure_tenant_id.strip() or settings.azure_authority.strip())
        and settings.sharepoint_site_id.strip()
    )


def require_storage() -> None:
    if not storage_configured():
        raise StorageNotConfiguredError(
            "SharePoint storage is not configured. WSR templates and decks are stored "
            "only in SharePoint — set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
            "AZURE_CLIENT_SECRET and SHAREPOINT_SITE_ID in the backend .env and restart."
        )


def decks_folder() -> str:
    return sp._upload_folder().strip("/")


def templates_folder() -> str:
    configured = get_settings().sharepoint_template_folder.strip().strip("/")
    return configured or "Shared Documents/WSR Template"


def data_folder() -> str:
    configured = get_settings().sharepoint_data_folder.strip().strip("/")
    return configured or f"{decks_folder()}/_data"


# ── HTTP plumbing ─────────────────────────────────────────────────────────────

_token_lock = threading.Lock()
_token_cache: tuple[str, float] | None = None


def _get_token(*, force_refresh: bool = False) -> str:
    global _token_cache
    with _token_lock:
        now = time.monotonic()
        if not force_refresh and _token_cache and _token_cache[1] > now:
            return _token_cache[0]
        try:
            token = sp.get_sharepoint_access_token()
        except Exception as exc:  # noqa: BLE001
            raise StorageError(f"Could not sign in to SharePoint: {exc}") from exc
        _token_cache = (token, now + TOKEN_TTL_SECONDS)
        return token


def _describe_failure(response: requests.Response, action: str) -> StorageError:
    status = response.status_code
    detail = (response.text or "")[:300]
    hint = ""
    if status in (401, 403):
        hint = " Check the Entra app permissions (Sites.ReadWrite.All) and admin consent."
    return StorageError(f"SharePoint {action} failed ({status}).{hint} {detail}".strip())


def _request(
    method: str,
    url: str,
    *,
    timeout: float = 120,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    retries: int = 3,
) -> requests.Response:
    refreshed = False
    attempt = 0
    while True:
        attempt += 1
        merged = {"Authorization": f"Bearer {_get_token()}", **(headers or {})}
        try:
            response = requests.request(
                method, url, headers=merged, data=data, timeout=timeout
            )
        except requests.RequestException as exc:
            if attempt >= retries:
                raise StorageError(f"SharePoint is unreachable: {exc}") from exc
            time.sleep(min(2 ** (attempt - 1), 8))
            continue

        if response.status_code == 401 and not refreshed:
            refreshed = True
            _get_token(force_refresh=True)
            continue
        if response.status_code in _RETRY_STATUSES and attempt < retries:
            try:
                wait = float(response.headers.get("Retry-After", 2 ** (attempt - 1)))
            except ValueError:
                wait = 2 ** (attempt - 1)
            time.sleep(min(wait, 10))
            continue
        return response


# ── Listing cache ─────────────────────────────────────────────────────────────

_listing_lock = threading.Lock()
_listing_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def invalidate_listing(folder: str | None = None) -> None:
    with _listing_lock:
        if folder is None:
            _listing_cache.clear()
        else:
            _listing_cache.pop(folder.strip("/"), None)


# ── Public API ────────────────────────────────────────────────────────────────

def list_folder(folder: str, *, use_cache: bool = True) -> list[dict[str, Any]]:
    """Files (not sub-folders) directly inside ``folder``. A missing folder is empty."""
    require_storage()
    key = folder.strip("/")
    now = time.monotonic()
    if use_cache:
        with _listing_lock:
            cached = _listing_cache.get(key)
            if cached and cached[0] > now:
                return list(cached[1])

    items: list[dict[str, Any]] = []
    url: str | None = f"{sp._build_sharepoint_children_url(key)}?$top=200"
    while url:
        response = _request("GET", url, timeout=60)
        if response.status_code == 404:
            items = []
            break
        if response.status_code != 200:
            raise _describe_failure(response, f"folder listing of '{key}'")
        payload = response.json()
        for raw in payload.get("value", []):
            if "folder" in raw:
                continue
            items.append(sp.normalize_sharepoint_item(raw))
        url = payload.get("@odata.nextLink")

    with _listing_lock:
        _listing_cache[key] = (time.monotonic() + LISTING_TTL_SECONDS, items)
    return list(items)


def get_item(folder: str, filename: str) -> dict[str, Any] | None:
    """Normalised drive item, or None when the file does not exist."""
    require_storage()
    response = _request("GET", sp._build_sharepoint_item_url(folder, filename), timeout=60)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise _describe_failure(response, f"lookup of '{filename}'")
    return sp.normalize_sharepoint_item(response.json())


def upload_file(
    local_path: Path,
    folder: str,
    filename: str | None = None,
    *,
    mime: str | None = None,
) -> dict[str, Any]:
    """Upload ``local_path`` into ``folder`` (folders are created by path). Returns the item."""
    require_storage()
    local_path = Path(local_path)
    if not local_path.is_file():
        raise FileNotFoundError(f"File not found: {local_path}")
    name = filename or local_path.name
    content_type = mime or _MIME_BY_SUFFIX.get(Path(name).suffix.lower(), "application/octet-stream")

    response = _request(
        "PUT",
        sp._build_sharepoint_upload_url(folder, name),
        timeout=300,
        headers={"Content-Type": content_type},
        data=local_path.read_bytes(),
    )
    if response.status_code not in (200, 201):
        raise _describe_failure(response, f"upload of '{name}' to '{folder}'")
    item = sp.normalize_sharepoint_item(response.json())
    invalidate_listing(folder)
    logger.info("Uploaded %s to SharePoint folder %s", name, folder)
    return item


def download_file(folder: str, filename: str, destination: Path) -> Path | None:
    """Download into ``destination`` atomically. Returns None when the file does not exist."""
    require_storage()
    response = _request(
        "GET", sp._build_sharepoint_upload_url(folder, filename), timeout=300
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise _describe_failure(response, f"download of '{filename}'")

    content = response.content
    if filename.lower().endswith(".pptx") and not content.startswith(b"PK"):
        raise StorageError(f"SharePoint returned '{filename}' but it is not a valid .pptx.")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(destination.name + ".download")
    temp_path.write_bytes(content)
    try:
        os.replace(temp_path, destination)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise

    # Keep the local mtime equal to SharePoint's so cached slide PNGs stay comparable.
    last_modified = response.headers.get("Last-Modified")
    if last_modified:
        try:
            stamp = parsedate_to_datetime(last_modified).timestamp()
            os.utime(destination, (stamp, stamp))
        except (TypeError, ValueError, OSError):
            pass
    logger.info("Downloaded %s from SharePoint (%d bytes)", filename, len(content))
    return destination


def delete_file(folder: str, filename: str) -> bool:
    require_storage()
    response = _request("DELETE", sp._build_sharepoint_item_url(folder, filename), timeout=60)
    if response.status_code == 404:
        return False
    if response.status_code not in (200, 204):
        raise _describe_failure(response, f"delete of '{filename}'")
    invalidate_listing(folder)
    return True
