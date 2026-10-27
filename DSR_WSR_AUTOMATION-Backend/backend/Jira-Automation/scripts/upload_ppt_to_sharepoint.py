"""
Upload a local .pptx to a SharePoint shared library via Microsoft Graph.

Uses app-only (client credentials) auth — no user interaction required once
AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, and SHAREPOINT_SITE_ID
are set in .env.

Usage (from backend/Jira-Automation with venv active):

  python scripts/upload_ppt_to_sharepoint.py output/WSR_2026-10-13_2026-10-17.pptx

Optional: override the remote folder for this run only:

  python scripts/upload_ppt_to_sharepoint.py output/WSR_....pptx --folder "Shared Documents/WSR/2026"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload a WSR .pptx to SharePoint via Microsoft Graph (app-only auth)"
    )
    parser.add_argument("pptx", help="Path to the local .pptx file")
    parser.add_argument(
        "--folder",
        default=None,
        help="Override SHAREPOINT_UPLOAD_FOLDER for this run (e.g. 'Shared Documents/WSR/2026')",
    )
    args = parser.parse_args()

    ppt_path = Path(args.pptx).resolve()
    if not ppt_path.is_file():
        print(f"Error: file not found: {ppt_path}")
        return 1

    # Optional folder override
    if args.folder:
        import os
        os.environ["SHAREPOINT_UPLOAD_FOLDER"] = args.folder
        # Reset the settings cache so the new value is picked up
        from app.config import get_settings
        get_settings.cache_clear()

    from app.services.sharepoint_upload_service import upload_ppt_to_sharepoint

    print(f"Uploading: {ppt_path.name}")
    try:
        item = upload_ppt_to_sharepoint(ppt_path)
        web_url = item["webUrl"]
    except Exception as exc:
        print(f"Upload failed: {exc}")
        return 1

    print("Uploaded successfully.")
    print(f"Open in SharePoint: {web_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
