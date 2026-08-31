# WSR Google Drive Upload — Setup Guide

This guide walks through enabling **automatic WSR `.pptx` upload to Google Drive** using your GCP account. The same WSR pipeline used for OneDrive now supports Google Drive via `CLOUD_UPLOAD_PROVIDER=google_drive`.

---

## Overview

| Item | Detail |
|------|--------|
| **API** | Google Drive API v3 |
| **Auth** | OAuth 2.0 Desktop app (browser consent once, refresh token cached) |
| **Upload target** | Folder `WSR/` (configurable) in the signed-in user's Google Drive |
| **When upload runs** | After WSR generation and after in-browser editor sync |
| **Frontend** | Toolbar shows **Open in Google Drive** when upload succeeds |

---

## Step 1 — GCP project setup

1. Sign in to [Google Cloud Console](https://console.cloud.google.com/) with your GCP account.
2. Create a new project (or select an existing one with free credits).
3. Go to **APIs & Services → Library**.
4. Search for **Google Drive API** and click **Enable**.

---

## Step 2 — OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**.
2. Choose **External** (fine for testing with your own account) or **Internal** if you have Google Workspace.
3. Fill in app name, support email, and developer contact.
4. On **Scopes**, add:
   - `.../auth/drive.file` (see files created by this app)
5. Add your Google account under **Test users** while the app is in **Testing** mode.

---

## Step 3 — Create OAuth desktop credentials

1. Go to **APIs & Services → Credentials**.
2. **Create credentials → OAuth client ID**.
3. Application type: **Desktop app**.
4. Download the JSON file.
5. Save it in the backend repo as:

```
DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation/credentials/google-oauth-client.json
```

This path is gitignored — do not commit it.

---

## Step 4 — Backend environment variables

Edit `DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation/.env`:

```env
CLOUD_UPLOAD_PROVIDER=google_drive
GOOGLE_DRIVE_UPLOAD_ENABLED=true
GOOGLE_DRIVE_UPLOAD_FOLDER=WSR
GOOGLE_DRIVE_CLIENT_SECRET_FILE=credentials/google-oauth-client.json
```

| Variable | Description |
|----------|-------------|
| `CLOUD_UPLOAD_PROVIDER` | Set to `google_drive` (or `onedrive` for Microsoft) |
| `GOOGLE_DRIVE_UPLOAD_ENABLED` | Must be `true` |
| `GOOGLE_DRIVE_UPLOAD_FOLDER` | Subfolder name in Google Drive (default `WSR`) |
| `GOOGLE_DRIVE_CLIENT_SECRET_FILE` | Path to OAuth client JSON |

Only **one** cloud provider is active at a time.

---

## Step 5 — Install Python dependencies

From `backend/Jira-Automation` with your virtual environment active:

```powershell
pip install -r requirements.txt
```

New packages: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`.

---

## Step 6 — First-time Google sign-in (token cache)

The API server cannot open a browser during background WSR jobs. Run this **once** on the same machine as the backend:

```powershell
cd DSR_WSR_AUTOMATION-Backend\backend\Jira-Automation
python scripts/upload_ppt_to_google_drive.py output\WSR_2026-07-27_2026-07-31.pptx
```

(Use any existing `.pptx` path, or generate a WSR first.)

1. A browser window opens for Google sign-in.
2. Approve access to Google Drive.
3. Script uploads the file and prints the Drive link.
4. Token is saved to `.google_drive_token.json` (gitignored).

**Restart the backend** after this step.

---

## Step 7 — Generate a WSR from the UI

1. Start backend and frontend.
2. **Intake** → import story data.
3. **Generate WSR** → pick week + template.
4. When generation completes, the toolbar should show **Open in Google Drive**.

Metadata is also saved locally:

```
output/WSR_{start}_{end}_cloud.json
output/WSR_{start}_{end}_google_drive.json
```

---

## Architecture

```
WSRReportPanel (frontend)
    → POST /api/wsr/generate
    → wsr_service.generate_wsr_deck()
    → cloud_upload_service.try_upload_wsr_ppt()
    → google_drive_upload_service.upload_ppt_to_google_drive()
    → Drive API: create/update file in WSR/ folder
    → returns webViewLink → cloud_web_url in API response
```

**Key files:**

| File | Purpose |
|------|---------|
| `app/services/google_drive_upload_service.py` | Drive API upload + OAuth |
| `app/services/cloud_upload_service.py` | Provider dispatcher |
| `scripts/upload_ppt_to_google_drive.py` | First-time auth CLI |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Google OAuth client secret not found` | Place JSON at `credentials/google-oauth-client.json` |
| `No Google Drive token available` | Run `upload_ppt_to_google_drive.py` interactively once |
| `access_denied` on consent screen | Add your account as a **Test user** on OAuth consent screen |
| No **Open in Google Drive** button | Check `GOOGLE_DRIVE_UPLOAD_ENABLED=true` and backend logs |
| Token expired | Re-run the CLI script; refresh token should auto-renew |
| Upload works in CLI but not from UI | Ensure backend runs on same machine with `.google_drive_token.json` |

Upload failures do **not** block WSR generation — **Download PPT** always works from local `output/`.

---

## Switching back to OneDrive

```env
CLOUD_UPLOAD_PROVIDER=onedrive
ONEDRIVE_UPLOAD_ENABLED=true
GOOGLE_DRIVE_UPLOAD_ENABLED=false
```

---

## Security notes

- Keep `credentials/google-oauth-client.json` and `.google_drive_token.json` private.
- Files upload to the **Google account used during sign-in**.
- Scope `drive.file` limits access to files/folders created by this app.

---

## Next steps (optional)

- **Shared Drive / team folder** — requires a service account or broader Drive scope + Shared Drive ID.
- **SharePoint** — separate Microsoft Graph integration (see `docs/WSR_SHAREPOINT_ONEDRIVE_UPLOAD_GUIDE.md`).
