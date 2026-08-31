"""Upload generated WSR decks to Google Drive via Drive API v3 (OAuth refresh token)."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from app.config import get_settings
from app.paths import OUTPUT_DIR, REPO_ROOT

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
PPT_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
TOKEN_PATH = REPO_ROOT / ".google_drive_token.json"
FOLDER_CACHE_PATH = REPO_ROOT / ".google_drive_folder.json"


def _client_secret_path() -> Path:
    settings = get_settings()
    configured = settings.google_drive_client_secret_file.strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path
    default = REPO_ROOT / "credentials" / "google-oauth-client.json"
    return default


def _read_oauth_client_type(secret_path: Path) -> str:
    """Return ``installed`` or ``web`` from the GCP OAuth client JSON."""
    data = json.loads(secret_path.read_text(encoding="utf-8"))
    if "installed" in data:
        return "installed"
    if "web" in data:
        return "web"
    raise RuntimeError(
        f"Unrecognized OAuth client JSON at {secret_path}. "
        "Create a Desktop app OAuth client in GCP Console."
    )


# Fixed loopback port — must match Authorized redirect URI in GCP (Web client)
OAUTH_LOCAL_PORT = 8080
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_LOCAL_PORT}/"


def _run_interactive_oauth_flow(secret_path: Path):
    """Browser OAuth sign-in on a fixed localhost port (8080)."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_type = _read_oauth_client_type(secret_path)
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)

    print(
        f"Opening browser for Google sign-in (redirect: {OAUTH_REDIRECT_URI})\n"
        "If you see redirect_uri_mismatch, add this URI in GCP Console:\n"
        "  APIs & Services → Credentials → your OAuth client →\n"
        f"  Authorized redirect URIs → {OAUTH_REDIRECT_URI}\n"
        f"  (also add http://127.0.0.1:{OAUTH_LOCAL_PORT}/ if needed)\n"
        f"Client type in JSON: {client_type}"
    )
    return flow.run_local_server(
        host="localhost",
        port=OAUTH_LOCAL_PORT,
        open_browser=True,
        redirect_uri_trailing_slash=True,
        access_type="offline",
        prompt="consent",
    )


def _get_credentials(*, interactive: bool = False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = None
    if TOKEN_PATH.is_file():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("Google Drive access token refreshed silently (no browser needed)")
        elif interactive:
            secret_path = _client_secret_path()
            if not secret_path.is_file():
                raise RuntimeError(
                    f"Google OAuth client secret not found: {secret_path}. "
                    "Download from GCP Console → APIs & Services → Credentials."
                )
            creds = _run_interactive_oauth_flow(secret_path)
        else:
            raise RuntimeError(
                "No Google Drive token available. "
                "Run: python scripts/upload_ppt_to_google_drive.py path/to/deck.pptx"
            )

    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _get_drive_service(*, interactive: bool = False):
    from googleapiclient.discovery import build

    creds = _get_credentials(interactive=interactive)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _load_cached_folder_id(folder_name: str) -> str | None:
    if not FOLDER_CACHE_PATH.is_file():
        return None
    try:
        data = json.loads(FOLDER_CACHE_PATH.read_text(encoding="utf-8"))
        if data.get("folder_name") == folder_name and data.get("folder_id"):
            return str(data["folder_id"])
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def _save_cached_folder_id(folder_name: str, folder_id: str) -> None:
    FOLDER_CACHE_PATH.write_text(
        json.dumps({"folder_name": folder_name, "folder_id": folder_id}, indent=2),
        encoding="utf-8",
    )


def _get_or_create_folder(service, folder_name: str) -> str:
    cached = _load_cached_folder_id(folder_name)
    if cached:
        try:
            service.files().get(fileId=cached, fields="id, trashed").execute()
            return cached
        except Exception:
            logger.warning("Cached Google Drive folder id invalid; recreating folder")

    query = (
        "mimeType='application/vnd.google-apps.folder' "
        f"and name='{folder_name.replace(chr(39), '')}' "
        "and trashed=false"
    )
    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name)", pageSize=1)
        .execute()
    )
    files = results.get("files", [])
    if files:
        folder_id = files[0]["id"]
        _save_cached_folder_id(folder_name, folder_id)
        return folder_id

    created = (
        service.files()
        .create(
            body={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            },
            fields="id",
        )
        .execute()
    )
    folder_id = created["id"]
    _save_cached_folder_id(folder_name, folder_id)
    return folder_id


def _find_file_in_folder(service, folder_id: str, filename: str) -> str | None:
    safe_name = filename.replace("'", "\\'")
    query = (
        f"name='{safe_name}' and '{folder_id}' in parents and trashed=false"
    )
    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id)", pageSize=1)
        .execute()
    )
    files = results.get("files", [])
    return files[0]["id"] if files else None


def upload_ppt_to_google_drive(
    ppt_path: Path,
    *,
    remote_filename: str | None = None,
    interactive: bool = False,
) -> str:
    """Upload a local .pptx to the configured Google Drive folder. Returns webViewLink."""
    from googleapiclient.http import MediaFileUpload

    ppt_path = ppt_path.resolve()
    if not ppt_path.is_file():
        raise FileNotFoundError(f"PPT not found: {ppt_path}")

    settings = get_settings()
    folder_name = settings.google_drive_upload_folder.strip() or "WSR"
    filename = remote_filename or ppt_path.name

    service = _get_drive_service(interactive=interactive)
    folder_id = _get_or_create_folder(service, folder_name)
    media = MediaFileUpload(str(ppt_path), mimetype=PPT_MIME, resumable=True)

    existing_id = _find_file_in_folder(service, folder_id, filename)
    if existing_id:
        updated = (
            service.files()
            .update(
                fileId=existing_id,
                media_body=media,
                fields="id, webViewLink",
            )
            .execute()
        )
        web_url = updated.get("webViewLink")
    else:
        created = (
            service.files()
            .create(
                body={"name": filename, "parents": [folder_id]},
                media_body=media,
                fields="id, webViewLink",
            )
            .execute()
        )
        web_url = created.get("webViewLink")

    if not web_url:
        raise RuntimeError("Upload succeeded but Drive did not return webViewLink")
    return str(web_url)


def google_drive_meta_path(start_date: date, end_date: date) -> Path:
    return OUTPUT_DIR / f"WSR_{start_date}_{end_date}_google_drive.json"


def save_google_drive_web_url(start_date: date, end_date: date, web_url: str) -> None:
    path = google_drive_meta_path(start_date, end_date)
    path.write_text(
        json.dumps({"webUrl": web_url, "provider": "google_drive"}, indent=2),
        encoding="utf-8",
    )


def load_google_drive_web_url(start_date: date, end_date: date) -> str | None:
    path = google_drive_meta_path(start_date, end_date)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        url = data.get("webUrl")
        return str(url) if url else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def try_upload_wsr_ppt_to_google_drive(
    ppt_path: Path,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    interactive: bool = False,
) -> str | None:
    """Upload when Google Drive is the active provider; log and return None on failure."""
    settings = get_settings()
    if not settings.google_drive_upload_enabled:
        return None
    if not _client_secret_path().is_file() and not TOKEN_PATH.is_file():
        logger.warning(
            "GOOGLE_DRIVE upload enabled but OAuth client secret / token missing"
        )
        return None

    try:
        web_url = upload_ppt_to_google_drive(ppt_path, interactive=interactive)
        if start_date is not None and end_date is not None:
            save_google_drive_web_url(start_date, end_date, web_url)
        logger.info("Uploaded WSR deck to Google Drive: %s", web_url)
        return web_url
    except Exception as exc:
        logger.warning("Google Drive upload failed: %s", exc)
        print(f"Warning: Google Drive upload failed: {exc}")
        return None
