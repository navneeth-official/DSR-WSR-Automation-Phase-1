"""
Upload a local .pptx to personal OneDrive via Microsoft Graph.

First run opens a device-code sign-in in the terminal; later runs reuse
``.msal_token_cache.bin`` in the Jira-Automation folder.

Usage (from backend/Jira-Automation with venv active):

  python scripts/upload_ppt_to_onedrive.py output/WSR_2026-07-27_2026-07-31.pptx
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
        print("Usage: python scripts/upload_ppt_to_onedrive.py <path-to.pptx>")
        return 1

    ppt_path = Path(sys.argv[1]).resolve()
    if not ppt_path.is_file():
        print(f"File not found: {ppt_path}")
        return 1

    from app.services.onedrive_upload_service import upload_ppt_to_onedrive

    try:
        web_url = upload_ppt_to_onedrive(ppt_path, interactive=True)
    except Exception as exc:
        print(f"Upload failed: {exc}")
        return 1

    print(f"Uploaded successfully.")
    print(f"Open in OneDrive: {web_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
