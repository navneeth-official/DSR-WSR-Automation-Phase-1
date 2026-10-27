"""Upload generated WSR decks to a SharePoint shared library via Microsoft Graph.

Uses app-only authentication (client credentials / client secret) so the upload
runs fully unattended — no user interaction or token cache file required.

The Entra app registration must have:
  • Application permission: Sites.ReadWrite.All  (admin consent required)
  • Application permission: Files.ReadWrite.All  (or scoped via site permission)

Upload URL logic
----------------
If SHAREPOINT_DRIVE_ID is set:
    PUT /drives/{drive_id}/root:/{folder}/{filename}:/content

Otherwise (default document library of a site):
    PUT /sites/{site_id}/drive/root:/{folder}/{filename}:/content

The same item path (without ``:/content``) is used to read the item's metadata
(eTag, lastModifiedDateTime, …) and, with ``:/content``, to download the file again
for the "Re-check deck" flow.

Set CLOUD_UPLOAD_PROVIDER=sharepoint in .env to activate this provider.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

import msal
import requests

from app.config import get_settings
from app.paths import wsr_sharepoint_meta_path

logger = logging.getLogger(__name__)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
# App-only scope — client credentials flow uses /.default
GRAPH_APP_SCOPE = ["https://graph.microsoft.com/.default"]
PPT_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


def _resolve_authority() -> str:
    settings = get_settings()
    if settings.azure_authority.strip():
        return settings.azure_authority.strip()
    tenant = settings.azure_tenant_id.strip()
    if not tenant:
        raise RuntimeError(
            "AZURE_TENANT_ID must be set for SharePoint app-only auth. "
            "Consumer accounts are not supported."
        )
    return f"https://login.microsoftonline.com/{tenant}"


def get_sharepoint_access_token() -> str:
    """Return a Graph access token using app-only (client credentials) flow.

    No user interaction needed — uses AZURE_CLIENT_ID + AZURE_CLIENT_SECRET.
    Token is acquired fresh each call; MSAL caches it in memory automatically.
    """
    settings = get_settings()
    client_id = settings.azure_client_id.strip()
    client_secret = settings.azure_client_secret.strip()

    if not client_id:
        raise RuntimeError("AZURE_CLIENT_ID is not set")
    if not client_secret:
        raise RuntimeError(
            "AZURE_CLIENT_SECRET is not set. "
            "SharePoint app-only auth requires a client secret."
        )

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=_resolve_authority(),
        client_credential=client_secret,
    )

    result = app.acquire_token_for_client(scopes=GRAPH_APP_SCOPE)

    if not result or "access_token" not in result:
        error = result.get("error_description", result.get("error", "unknown"))
        raise RuntimeError(f"Failed to acquire SharePoint token: {error}")

    return str(result["access_token"])


def _build_sharepoint_item_url(folder: str, filename: str) -> str:
    """Graph URL of a drive item addressed by path (no ``:/content`` suffix)."""
    settings = get_settings()
    site_id = settings.sharepoint_site_id.strip()
    drive_id = settings.sharepoint_drive_id.strip()

    if not site_id:
        raise RuntimeError(
            "SHAREPOINT_SITE_ID is not set. "
            "Get it from your SharePoint admin or via: "
            "GET https://graph.microsoft.com/v1.0/sites/{hostname}:/{site-path}"
        )

    folder = folder.strip().strip("/")
    filename = filename.strip().lstrip("/")
    item_path = f"{folder}/{filename}" if folder else filename

    if drive_id:
        # Explicit drive (e.g. a specific document library, not the default one)
        return f"{GRAPH_ROOT}/drives/{drive_id}/root:/{item_path}:"
    # Default document library of the site
    return f"{GRAPH_ROOT}/sites/{site_id}/drive/root:/{item_path}:"


def _build_sharepoint_upload_url(folder: str, filename: str) -> str:
    """Build the Graph API PUT URL for the target SharePoint document library."""
    return f"{_build_sharepoint_item_url(folder, filename)}/content"


def _upload_folder() -> str:
    return get_settings().sharepoint_upload_folder.strip() or "Shared Documents/WSR"


def normalize_sharepoint_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce a Graph driveItem to the fields we persist."""
    parent = payload.get("parentReference") or {}
    return {
        "webUrl": payload.get("webUrl"),
        "id": payload.get("id"),
        "eTag": payload.get("eTag") or payload.get("cTag"),
        "lastModifiedDateTime": payload.get("lastModifiedDateTime"),
        "name": payload.get("name"),
        "size": payload.get("size"),
        "driveId": parent.get("driveId"),
    }


def upload_ppt_to_sharepoint(
    ppt_path: Path,
    *,
    remote_filename: str | None = None,
) -> dict[str, Any]:
    """Upload a local .pptx to the configured SharePoint library.

    Returns the normalised SharePoint item (``webUrl``, ``id``, ``eTag``, …).
    Raises RuntimeError on failure.
    """
    ppt_path = ppt_path.resolve()
    if not ppt_path.is_file():
        raise FileNotFoundError(f"PPT not found: {ppt_path}")

    filename = remote_filename or ppt_path.name
    url = _build_sharepoint_upload_url(_upload_folder(), filename)
    token = get_sharepoint_access_token()

    logger.info("Uploading %s to SharePoint: %s", filename, url)

    with ppt_path.open("rb") as handle:
        response = requests.put(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": PPT_MIME,
            },
            data=handle,
            timeout=300,
        )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"SharePoint upload failed ({response.status_code}): {response.text}"
        )

    item = normalize_sharepoint_item(response.json())
    if not item.get("webUrl"):
        raise RuntimeError("Upload succeeded but Graph did not return webUrl")

    logger.info("Uploaded to SharePoint: %s", item["webUrl"])
    return item


# ── Read side: metadata + download (used by "Re-check deck") ──────────────────

def get_sharepoint_item_metadata(filename: str) -> dict[str, Any]:
    """Return the normalised drive item for ``filename`` in the upload folder.

    Raises FileNotFoundError when the file is not in SharePoint, RuntimeError for
    any other Graph failure.
    """
    url = _build_sharepoint_item_url(_upload_folder(), filename)
    token = get_sharepoint_access_token()
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if response.status_code == 404:
        raise FileNotFoundError(f"{filename} was not found in SharePoint.")
    if response.status_code != 200:
        raise RuntimeError(
            f"SharePoint metadata lookup failed ({response.status_code}): {response.text[:300]}"
        )
    return normalize_sharepoint_item(response.json())


def download_ppt_from_sharepoint(filename: str, destination: Path) -> Path:
    """Download ``filename`` from SharePoint and atomically replace ``destination``.

    The file is written to a sibling temp file first so a failed or partial download
    never corrupts the existing local deck.
    """
    url = _build_sharepoint_upload_url(_upload_folder(), filename)
    token = get_sharepoint_access_token()
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=300,
    )
    if response.status_code == 404:
        raise FileNotFoundError(f"{filename} was not found in SharePoint.")
    if response.status_code != 200:
        raise RuntimeError(
            f"SharePoint download failed ({response.status_code}): {response.text[:300]}"
        )
    content = response.content
    # .pptx is a zip container; refuse to overwrite the deck with an HTML error page etc.
    if not content.startswith(b"PK"):
        raise RuntimeError("SharePoint returned a file that is not a valid .pptx.")

    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(destination.name + ".download")
    temp_path.write_bytes(content)
    try:
        os.replace(temp_path, destination)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise
    logger.info("Downloaded %s from SharePoint (%d bytes)", filename, len(content))
    return destination


# ── Metadata helpers (mirrors OneDrive pattern) ───────────────────────────────

def sharepoint_meta_path(start_date: date, end_date: date, *, variant: int = 1) -> Path:
    return wsr_sharepoint_meta_path(start_date, end_date, variant=variant)


def save_sharepoint_item_meta(
    start_date: date,
    end_date: date,
    item: dict[str, Any],
    *,
    variant: int = 1,
) -> None:
    """Persist the full SharePoint item (webUrl, id, eTag, …) for one deck variant."""
    path = sharepoint_meta_path(start_date, end_date, variant=variant)
    payload = {**item, "variant": variant}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_sharepoint_item_meta(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
) -> dict[str, Any] | None:
    path = sharepoint_meta_path(start_date, end_date, variant=variant)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_sharepoint_web_url(
    start_date: date,
    end_date: date,
    web_url: str,
    *,
    variant: int = 1,
) -> None:
    """Back-compat helper: store only the web URL."""
    save_sharepoint_item_meta(start_date, end_date, {"webUrl": web_url}, variant=variant)


def load_sharepoint_web_url(
    start_date: date,
    end_date: date,
    *,
    variant: int = 1,
) -> str | None:
    data = load_sharepoint_item_meta(start_date, end_date, variant=variant)
    url = (data or {}).get("webUrl")
    return str(url) if url else None


def try_upload_wsr_ppt(
    ppt_path: Path,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    variant: int = 1,
) -> str | None:
    """Upload when enabled in settings; log and return None on failure."""
    settings = get_settings()
    if not settings.sharepoint_upload_enabled:
        return None
    if not settings.azure_client_id.strip():
        logger.warning("SHAREPOINT_UPLOAD_ENABLED but AZURE_CLIENT_ID is not set")
        return None
    if not settings.sharepoint_site_id.strip():
        logger.warning("SHAREPOINT_UPLOAD_ENABLED but SHAREPOINT_SITE_ID is not set")
        return None

    try:
        item = upload_ppt_to_sharepoint(ppt_path)
        if start_date is not None and end_date is not None:
            save_sharepoint_item_meta(start_date, end_date, item, variant=variant)
        logger.info("Uploaded WSR deck to SharePoint: %s", item["webUrl"])
        return str(item["webUrl"])
    except Exception as exc:
        logger.warning("SharePoint upload failed: %s", exc)
        print(f"Warning: SharePoint upload failed: {exc}")
        return None
