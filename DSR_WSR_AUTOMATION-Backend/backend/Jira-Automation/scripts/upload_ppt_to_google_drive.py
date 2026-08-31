"""
Upload a local .pptx to Google Drive via Drive API v3.

First run opens a browser OAuth consent flow; later runs reuse
``.google_drive_token.json`` in the Jira-Automation folder.

Prerequisites:
  1. Enable Google Drive API in your GCP project
  2. Create OAuth 2.0 Desktop client credentials
  3. Save JSON as credentials/google-oauth-client.json (or set GOOGLE_DRIVE_CLIENT_SECRET_FILE)
  4. Set CLOUD_UPLOAD_PROVIDER=google_drive and GOOGLE_DRIVE_UPLOAD_ENABLED=true in .env

Usage (from backend/Jira-Automation with venv active):

  python scripts/upload_ppt_to_google_drive.py output/WSR_2026-07-27_2026-07-31.pptx
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/upload_ppt_to_google_drive.py <path-to.pptx>")
        return 1

    ppt_path = Path(sys.argv[1]).resolve()
    if not ppt_path.is_file():
        print(f"File not found: {ppt_path}")
        return 1

    from app.services.google_drive_upload_service import upload_ppt_to_google_drive

    try:
        web_url = upload_ppt_to_google_drive(ppt_path, interactive=True)
    except Exception as exc:
        print(f"Upload failed: {exc}")
        return 1

    print("Uploaded successfully.")
    print(f"Open in Google Drive: {web_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
