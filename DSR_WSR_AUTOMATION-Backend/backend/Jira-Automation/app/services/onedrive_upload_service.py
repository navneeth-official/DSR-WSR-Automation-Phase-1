"""Upload generated WSR decks to personal OneDrive via Microsoft Graph (delegated MSAL)."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import msal
import requests

from app.config import get_settings
from app.paths import OUTPUT_DIR, REPO_ROOT

logger = logging.getLogger(__name__)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/Files.ReadWrite"]
PPT_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
TOKEN_CACHE_PATH = REPO_ROOT / ".msal_token_cache.bin"


def _resolve_authority() -> str:
    settings = get_settings()
    if settings.azure_authority.strip():
        return settings.azure_authority.strip()
    tenant = settings.azure_tenant_id.strip()
    if tenant:
        return f"https://login.microsoftonline.com/{tenant}"
    return "https://login.microsoftonline.com/consumers"


def _load_token_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE_PATH.is_file():
        cache.deserialize(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
    return cache


def _save_token_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        TOKEN_CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")


def get_graph_access_token(*, interactive: bool = False) -> str:
    """
    Return a Graph access token using cached MSAL session.

    First-time sign-in: run ``python scripts/upload_ppt_to_onedrive.py <ppt>``
    (device code flow) or call with ``interactive=True`` on a machine with a browser.
    """
    settings = get_settings()
    client_id = settings.azure_client_id.strip()
    if not client_id:
        raise RuntimeError("AZURE_CLIENT_ID is not set")

    cache = _load_token_cache()
    app = msal.PublicClientApplication(
        client_id,
        authority=_resolve_authority(),
        token_cache=cache,
    )

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPE, account=accounts[0])

    if not result and interactive:
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPE)
        if "user_code" not in flow:
            raise RuntimeError(f"Device code flow failed: {flow}")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)

    _save_token_cache(cache)

    if not result or "access_token" not in result:
        raise RuntimeError(
            "No Microsoft Graph token available. "
            "Run: python scripts/upload_ppt_to_onedrive.py path/to/deck.pptx"
        )

    return result["access_token"]


def _build_onedrive_upload_url(folder: str, filename: str) -> str:
    folder = folder.strip().strip("/")
    filename = filename.strip().lstrip("/")
    path = f"{folder}/{filename}" if folder else filename
    return f"{GRAPH_ROOT}/me/drive/root:/{path}:/content"


def upload_ppt_to_onedrive(
    ppt_path: Path,
    *,
    remote_filename: str | None = None,
    interactive: bool = False,
) -> str:
    """Upload a local .pptx to the configured OneDrive folder. Returns SharePoint/OneDrive webUrl."""
    ppt_path = ppt_path.resolve()
    if not ppt_path.is_file():
        raise FileNotFoundError(f"PPT not found: {ppt_path}")

    settings = get_settings()
    folder = settings.onedrive_upload_folder.strip() or "WSR"
    filename = remote_filename or ppt_path.name
    url = _build_onedrive_upload_url(folder, filename)
    token = get_graph_access_token(interactive=interactive)

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
            f"OneDrive upload failed ({response.status_code}): {response.text}"
        )

    payload = response.json()
    web_url = payload.get("webUrl")
    if not web_url:
        raise RuntimeError("Upload succeeded but Graph did not return webUrl")
    return str(web_url)


def onedrive_meta_path(start_date: date, end_date: date) -> Path:
    return OUTPUT_DIR / f"WSR_{start_date}_{end_date}_onedrive.json"


def save_onedrive_web_url(start_date: date, end_date: date, web_url: str) -> None:
    path = onedrive_meta_path(start_date, end_date)
    path.write_text(
        json.dumps({"webUrl": web_url}, indent=2),
        encoding="utf-8",
    )


def load_onedrive_web_url(start_date: date, end_date: date) -> str | None:
    path = onedrive_meta_path(start_date, end_date)
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
    interactive: bool = False,
) -> str | None:
    """Upload when enabled in settings; log and return None on failure."""
    settings = get_settings()
    if not settings.onedrive_upload_enabled:
        return None
    if not settings.azure_client_id.strip():
        logger.warning("ONEDRIVE_UPLOAD_ENABLED but AZURE_CLIENT_ID is not set")
        return None

    try:
        web_url = upload_ppt_to_onedrive(ppt_path, interactive=interactive)
        if start_date is not None and end_date is not None:
            save_onedrive_web_url(start_date, end_date, web_url)
        logger.info("Uploaded WSR deck to OneDrive: %s", web_url)
        return web_url
    except Exception as exc:
        logger.warning("OneDrive upload failed: %s", exc)
        print(f"Warning: OneDrive upload failed: {exc}")
        return None
