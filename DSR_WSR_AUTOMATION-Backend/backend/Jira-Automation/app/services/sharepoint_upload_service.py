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

Set CLOUD_UPLOAD_PROVIDER=sharepoint in .env to activate this provider.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import msal
import requests

from app.config import get_settings
from app.paths import OUTPUT_DIR

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


def _build_sharepoint_upload_url(folder: str, filename: str) -> str:
    """Build the Graph API PUT URL for the target SharePoint document library."""
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
        return f"{GRAPH_ROOT}/drives/{drive_id}/root:/{item_path}:/content"
    else:
        # Default document library of the site
        return f"{GRAPH_ROOT}/sites/{site_id}/drive/root:/{item_path}:/content"


def upload_ppt_to_sharepoint(
    ppt_path: Path,
    *,
    remote_filename: str | None = None,
) -> str:
    """Upload a local .pptx to the configured SharePoint library.

    Returns the SharePoint webUrl of the uploaded file.
    Raises RuntimeError on failure.
    """
    ppt_path = ppt_path.resolve()
    if not ppt_path.is_file():
        raise FileNotFoundError(f"PPT not found: {ppt_path}")

    settings = get_settings()
    folder = settings.sharepoint_upload_folder.strip() or "Shared Documents/WSR"
    filename = remote_filename or ppt_path.name
    url = _build_sharepoint_upload_url(folder, filename)
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

    payload = response.json()
    web_url = payload.get("webUrl")
    if not web_url:
        raise RuntimeError("Upload succeeded but Graph did not return webUrl")

    logger.info("Uploaded to SharePoint: %s", web_url)
    return str(web_url)


# ── Metadata helpers (mirrors OneDrive pattern) ───────────────────────────────

def sharepoint_meta_path(start_date: date, end_date: date) -> Path:
    return OUTPUT_DIR / f"WSR_{start_date}_{end_date}_sharepoint.json"


def save_sharepoint_web_url(start_date: date, end_date: date, web_url: str) -> None:
    path = sharepoint_meta_path(start_date, end_date)
    path.write_text(
        json.dumps({"webUrl": web_url}, indent=2),
        encoding="utf-8",
    )


def load_sharepoint_web_url(start_date: date, end_date: date) -> str | None:
    path = sharepoint_meta_path(start_date, end_date)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        url = data.get("webUrl")
        return str(url) if url else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def try_upload_wsr_ppt(
    ppt_path: Path,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
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
        web_url = upload_ppt_to_sharepoint(ppt_path)
        if start_date is not None and end_date is not None:
            save_sharepoint_web_url(start_date, end_date, web_url)
        logger.info("Uploaded WSR deck to SharePoint: %s", web_url)
        return web_url
    except Exception as exc:
        logger.warning("SharePoint upload failed: %s", exc)
        print(f"Warning: SharePoint upload failed: {exc}")
        return None
