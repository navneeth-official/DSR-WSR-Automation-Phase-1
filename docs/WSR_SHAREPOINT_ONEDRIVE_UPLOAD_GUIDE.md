# WSR Upload to OneDrive / SharePoint — Prerequisites & Steps

This guide explains how a generated WSR (Weekly Status Report) `.pptx` is written to cloud storage from the DSR-WSR Automation app, what you need before it works, and how the frontend and backend cooperate.

---

## Important: OneDrive vs SharePoint in this app

| What you may expect | What the app does today |
|---------------------|-------------------------|
| Upload to a **shared company SharePoint document library** (team site folder) | **Not implemented** — no `/sites/{site-id}/drive` integration |
| Upload to **OneDrive for Business** (the signed-in user's M365 drive) | **Implemented** — uses Microsoft Graph `PUT /me/drive/root:/…` |
| Manual upload via CLI script | **Supported** — works even when auto-upload is disabled |

For Microsoft 365 work accounts, OneDrive for Business is SharePoint-backed. The returned `webUrl` may look like a SharePoint URL, but the file lands in the **authenticated user's personal OneDrive**, under the folder configured by `ONEDRIVE_UPLOAD_FOLDER` (default: `WSR`).

To upload into a **shared org SharePoint folder**, the backend would need new Graph endpoints (site ID, drive ID, library path) and likely different permissions — see [Future: org SharePoint folder](#future-org-sharepoint-folder) at the end.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Frontend (React)                                                       │
│  Generate WSR → poll status → show "Open in OneDrive" if URL returned   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ REST API
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                                      │
│  1. Build WSR .pptx locally → output/WSR_{start}_{end}.pptx            │
│  2. If ONEDRIVE_UPLOAD_ENABLED → upload via Microsoft Graph             │
│  3. Save webUrl → output/WSR_{start}_{end}_onedrive.json                │
│  4. Return onedrive_web_url in API response                               │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ Microsoft Graph API
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  OneDrive for Business / personal OneDrive                              │
│  Path: {ONEDRIVE_UPLOAD_FOLDER}/WSR_{start}_{end}.pptx                  │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key point:** Upload runs on the **backend server**, not in the browser. The frontend never talks to Microsoft Graph directly.

---

## Prerequisites

### 1. Application stack running

| Component | Requirement |
|-----------|-------------|
| **PostgreSQL** | Jira/Rovo story data imported for the WSR week |
| **Backend** | FastAPI running from `DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation` |
| **Frontend** | React app running and pointed at the backend API |
| **WSR template** | At least one template uploaded via **Upload WSR Template** (stored locally on backend) |

### 2. Microsoft Entra (Azure AD) app registration

An admin (or you, if permitted) must register an app in [Microsoft Entra admin center](https://entra.microsoft.com).

| Setting | Value |
|---------|-------|
| **App type** | Public client application |
| **Supported account types** | Single tenant (org only) **or** multitenant — match your company M365 setup |
| **Public client flows** | Enabled (required for device-code sign-in) |
| **API permissions (delegated)** | `Microsoft Graph` → **`Files.ReadWrite`** |
| **Admin consent** | Grant org-wide consent if your tenant requires it |

You do **not** need a client secret — the app uses MSAL public-client + device-code flow.

Copy the **Application (client) ID** → this becomes `AZURE_CLIENT_ID`.

For a **work/school (G10X org) account**, also note your **Directory (tenant) ID** → `AZURE_TENANT_ID`.

### 3. Environment variables (backend `.env`)

Copy from `.env.example` and set:

```env
# Required for cloud upload
AZURE_CLIENT_ID=<your-application-client-id>

# For company M365 accounts (recommended for G10X)
AZURE_TENANT_ID=<your-directory-tenant-id>

# Optional — only if you need to override authority explicitly
# AZURE_AUTHORITY=https://login.microsoftonline.com/<tenant-id>

# Upload destination folder inside the signed-in user's OneDrive root
ONEDRIVE_UPLOAD_FOLDER=WSR

# Must be explicitly enabled (default is OFF)
ONEDRIVE_UPLOAD_ENABLED=true
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_CLIENT_ID` | Yes (if upload enabled) | empty | Entra app client ID |
| `AZURE_TENANT_ID` | Recommended for org accounts | empty | Restricts sign-in to your tenant |
| `AZURE_AUTHORITY` | No | derived from tenant | Full authority URL override |
| `ONEDRIVE_UPLOAD_FOLDER` | No | `WSR` | Subfolder under OneDrive root |
| `ONEDRIVE_UPLOAD_ENABLED` | Yes | `false` | Must be `true` for auto-upload |

### 4. Python dependencies

Already listed in `requirements.txt`:

- `msal>=1.28.0` — Microsoft authentication
- `requests>=2.31.0` — Graph HTTP upload

Install with your backend virtual environment active:

```powershell
cd DSR_WSR_AUTOMATION-Backend\backend\Jira-Automation
pip install -r requirements.txt
```

### 5. First-time Microsoft sign-in (token cache)

The API server uploads with **non-interactive** auth. It cannot open a browser login during WSR generation.

**One-time setup:** run the CLI upload script on the **same machine** where the backend runs. This performs device-code sign-in and creates `.msal_token_cache.bin` in the Jira-Automation folder.

```powershell
cd DSR_WSR_AUTOMATION-Backend\backend\Jira-Automation

# Activate your Python venv first, then:
python scripts/upload_ppt_to_onedrive.py output/WSR_2026-07-27_2026-07-31.pptx
```

Steps during first run:

1. Script prints a URL and a one-time code.
2. Open the URL in a browser and sign in with your **company Microsoft 365 account**.
3. Enter the code when prompted.
4. Approve **`Files.ReadWrite`** consent if asked.
5. Script uploads the file and prints `Open in OneDrive: https://…`.
6. Token cache is saved to `.msal_token_cache.bin` (gitignored).

**Restart the backend** after this so subsequent WSR generations reuse the cached token.

> **Note:** If the token expires and silent refresh fails, re-run the script above. Background jobs cannot trigger interactive login.

### 6. OneDrive folder layout

No manual folder creation is required — Graph creates the path on first upload.

| Item | Value |
|------|-------|
| Remote path | `{ONEDRIVE_UPLOAD_FOLDER}/{filename}.pptx` |
| Default folder | `WSR` |
| Example file | `WSR/WSR_2026-07-27_2026-07-31.pptx` |
| Overwrite behavior | Re-uploading the same filename **overwrites** the existing file |

---

## One-time setup checklist

Use this before expecting auto-upload from the UI:

- [ ] Register Entra public client app with Graph delegated `Files.ReadWrite`
- [ ] Grant admin consent (if required by your org)
- [ ] Set `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `ONEDRIVE_UPLOAD_ENABLED=true` in backend `.env`
- [ ] Set `ONEDRIVE_UPLOAD_FOLDER` if you want a folder other than `WSR`
- [ ] Run `python scripts/upload_ppt_to_onedrive.py output/<any-deck>.pptx` once to create token cache
- [ ] Confirm `.msal_token_cache.bin` exists in `backend/Jira-Automation/`
- [ ] Restart backend (`uvicorn`)
- [ ] Generate a test WSR and verify `output/WSR_*_onedrive.json` is created

---

## End-user steps (frontend)

These are the steps a report author follows in the UI after setup is complete.

### Step 1 — Import data (Intake)

1. Open the app sidebar → **Intake**.
2. Import Jira/Rovo JSON for the reporting week so stories exist in PostgreSQL.

### Step 2 — Upload or select a WSR template

1. Go to **Upload WSR Template** (or use an existing saved template).
2. This uploads a reference `.pptx` to **local backend storage** (`output/wsr_templates/`) — not to SharePoint.

### Step 3 — Generate the WSR

1. Go to **Weekly Reports → Generate WSR**.
2. Select the reporting week (Monday–Friday).
3. Choose the WSR template.
4. Click generate — the UI calls `POST /api/wsr/generate` and polls `GET /api/wsr/status`.

**Frontend files involved:**

| File | Role |
|------|------|
| `Frontend/src/app/App.tsx` | `GenerateWSRPage` hosts the generate flow |
| `Frontend/src/components/WSRReportPanel.tsx` | Triggers generation, shows toolbar actions |
| `Frontend/src/api/wsr.ts` | `startWsrJob()`, `waitForWsrJob()`, types include `onedrive_web_url` |

### Step 4 — Backend builds and optionally uploads

While the UI shows a loading spinner:

1. Backend builds slide content from the database.
2. WSR engine writes `output/WSR_{start}_{end}.pptx`.
3. If `ONEDRIVE_UPLOAD_ENABLED=true` and auth succeeds, backend uploads to OneDrive.
4. Backend saves `webUrl` to `output/WSR_{start}_{end}_onedrive.json`.
5. Status response includes `onedrive_web_url`.

### Step 5 — Open or download from the toolbar

When generation completes, the **WSR Report Panel** toolbar shows:

| Button | Action |
|--------|--------|
| **Download PPT** | Downloads from local backend via `GET /api/wsr/download` — always available |
| **Open in OneDrive** | Shown only when `onedrive_web_url` is present — opens the cloud copy in a new tab |

Relevant UI code:

```tsx
// WSRReportPanel.tsx — "Open in OneDrive" appears when backend returns a URL
{result?.onedrive_web_url ? (
  <a href={result.onedrive_web_url} target="_blank" rel="noopener noreferrer">
    Open in OneDrive
  </a>
) : null}
```

### Step 6 — Edit and re-sync (optional)

1. Edit slides in the in-browser PPT editor.
2. Changes auto-sync via `POST /api/wsr/editor/sync` (debounced ~700 ms).
3. Backend re-exports the local `.pptx` and **re-uploads to OneDrive** if upload is enabled.

> **Gap:** The editor sync API returns `onedrive_web_url`, but the frontend editor does not currently refresh the toolbar link after sync. The link from initial generation still works if the remote filename is unchanged.

### Step 7 — View existing reports

**Weekly Reports → View WSR** loads an on-disk deck via `WSRReportPanel` in viewer/editor mode. If a prior upload saved metadata, `load_onedrive_web_url()` may return the stored link when loading an existing week.

---

## Technical flow (backend)

### When upload is triggered

| Trigger | API / function | Upload called? |
|---------|----------------|----------------|
| WSR generation | `wsr_service.generate_wsr_deck()` → `try_upload_wsr_ppt()` | Yes (if enabled) |
| Editor sync | `POST /api/wsr/editor/sync` → `try_upload_wsr_ppt()` | Yes (if enabled) |
| Editor export | `POST /api/wsr/editor/export` | **No** |
| Manual CLI | `scripts/upload_ppt_to_onedrive.py` | Yes (always, bypasses enable flag) |

### Upload implementation

**Service:** `app/services/onedrive_upload_service.py`

```
try_upload_wsr_ppt()
  └─ if ONEDRIVE_UPLOAD_ENABLED && AZURE_CLIENT_ID
       └─ upload_ppt_to_onedrive()
            └─ get_graph_access_token(interactive=False)
            └─ PUT https://graph.microsoft.com/v1.0/me/drive/root:/{folder}/{file}:/content
            └─ return webUrl
       └─ save_onedrive_web_url() → output/WSR_{start}_{end}_onedrive.json
```

**Configuration:** `app/config.py`  
**Schema field:** `WsrGenerateResponse.onedrive_web_url` in `app/schemas/wsr.py`

### Local files created

| File | Purpose |
|------|---------|
| `output/WSR_{start}_{end}.pptx` | Generated deck |
| `output/WSR_{start}_{end}_onedrive.json` | `{"webUrl": "https://..."}` |
| `.msal_token_cache.bin` | Cached Microsoft tokens (do not commit) |

---

## Manual upload (without auto-upload)

If you prefer not to enable `ONEDRIVE_UPLOAD_ENABLED`, upload any deck manually:

```powershell
cd DSR_WSR_AUTOMATION-Backend\backend\Jira-Automation
python scripts/upload_ppt_to_onedrive.py output/WSR_2026-07-27_2026-07-31.pptx
```

This uses interactive device-code auth and uploads directly — useful for testing or one-off uploads.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No **Open in OneDrive** button | Upload disabled or failed silently | Set `ONEDRIVE_UPLOAD_ENABLED=true`; check backend logs |
| `No Microsoft Graph token available` | Token cache missing | Run `upload_ppt_to_onedrive.py` once interactively |
| `ONEDRIVE_UPLOAD_ENABLED but AZURE_CLIENT_ID is not set` | Missing env var | Set `AZURE_CLIENT_ID` in `.env` and restart backend |
| Upload works in CLI but not from UI | Backend runs as different user / no cache | Run CLI on same host/user as the backend process |
| `403` / consent errors | Missing permission or admin consent | Add `Files.ReadWrite` delegated; grant admin consent |
| Wrong tenant / can't sign in | Authority misconfigured | Set `AZURE_TENANT_ID` to your org tenant ID |
| File not in shared team folder | By design — uploads to **personal** OneDrive | See future SharePoint section below |
| Upload errors not shown in UI | Failures are logged, not surfaced | Check terminal/logs for `OneDrive upload failed:` |

Upload failures do **not** block WSR generation — the local `.pptx` and **Download PPT** still work.

---

## Security notes

- `.msal_token_cache.bin` contains refresh tokens — keep it on the server only; it is gitignored.
- Upload uses the **delegated identity** of whoever completed device-code sign-in — files appear in **that user's** OneDrive.
- For production, consider a dedicated service account and/or app-only auth if uploading to a shared library.

---

## Future: org SharePoint folder

To write WSR files into a **shared company SharePoint document library** (not personal OneDrive), the following would need to be added:

1. **Graph target change** — e.g.  
   `PUT /sites/{site-id}/drive/root:/{library-path}/{filename}:/content`  
   or upload to a specific drive ID.
2. **Configuration** — site URL, site ID, drive ID, folder path within the library.
3. **Permissions** — likely `Sites.ReadWrite.All` or `Files.ReadWrite.All` (delegated or application), plus SharePoint site access for the app or service principal.
4. **Auth model** — app-only (client credentials) is typical for unattended server upload to a shared folder; current code uses public client + device code.
5. **Frontend** — optional: folder picker, upload status, error display.

This is **not in the current codebase**. The existing `ONEDRIVE_UPLOAD_FOLDER` only creates a subfolder under `/me/drive`.

---

## Quick reference — key files

| Area | Path |
|------|------|
| Upload service | `DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation/app/services/onedrive_upload_service.py` |
| Config / env | `DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation/app/config.py`, `.env.example` |
| CLI auth + upload | `DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation/scripts/upload_ppt_to_onedrive.py` |
| Generate + upload hook | `DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation/app/services/wsr_service.py` |
| Editor sync + upload | `DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation/app/api/routes/wsr.py` |
| Frontend API types | `DSR-WSR-AUTOMATION-Frontend/Frontend/src/api/wsr.ts` |
| Frontend UI link | `DSR-WSR-AUTOMATION-Frontend/Frontend/src/components/WSRReportPanel.tsx` |

---

## Summary

1. **Prerequisites:** M365 Entra app, backend env vars, one-time device-code login, token cache on the backend host.
2. **User flow:** Intake → template → Generate WSR → **Open in OneDrive** (or Download PPT).
3. **Upload is backend-only** via Microsoft Graph to the signed-in user's OneDrive folder.
4. **Shared org SharePoint libraries** are not supported yet — only personal OneDrive (which for M365 is org-hosted but user-scoped).

For questions or to extend this to a team SharePoint library, coordinate with your M365 admin for site permissions and app registration changes.
