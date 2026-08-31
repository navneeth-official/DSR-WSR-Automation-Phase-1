# WSR slide preview — rendering options

WSR previews are PNG images exported from the `.pptx` after generation. **Layout fidelity depends entirely on the renderer.**

## Comparison

| Backend | Fidelity | Platform | Best for |
|---------|----------|----------|----------|
| **`com`** | Pixel-perfect (PowerPoint) | Windows + Office | Dev laptop, Windows VM |
| **`remote`** | Pixel-perfect (PowerPoint on another machine) | **Ubuntu VM** + Windows render host | **Production on GCP Linux** |
| **`libreoffice`** | Often wrong fonts, colors, spacing | Any Linux | Dev/test only — not recommended for production templates |
| **`auto`** | COM on Windows; remote if URL set; else LibreOffice | Mixed | Convenience |

LibreOffice re-implements PowerPoint — it is **not** a substitute for Office. Misaligned text and wrong colors are expected.

---

## Recommended: remote Windows COM render (production)

Keep the app on **Ubuntu GCP**. Run a small **Windows** render service (dev PC, office machine, or Windows VM) that uses real PowerPoint.

### 1. On Windows (PowerPoint + Python venv)

```powershell
cd DSR_WSR_AUTOMATION-Backend\backend\Jira-Automation
.venv\Scripts\activate
pip install pywin32 fastapi uvicorn python-multipart requests

$env:PPT_RENDER_SERVER_TOKEN = "choose-a-long-random-secret"
python scripts/ppt_render_server.py
# Listening on http://0.0.0.0:8765
```

Verify:

```powershell
curl http://localhost:8765/health
# {"status":"ok","renderer":"com"}
```

### 2. Network access from Ubuntu VM → Windows

Pick one:

- **Same LAN / VPN** — use private IP, e.g. `http://10.0.0.5:8765`
- **SSH tunnel from VM** (Windows reachable via jump host):

  ```bash
  ssh -L 8765:127.0.0.1:8765 user@windows-host
  # VM .env: PPT_RENDER_REMOTE_URL=http://127.0.0.1:8765
  ```

- **Reverse SSH** (Windows initiates tunnel to VM) for NAT/home PCs

Firewall: allow inbound **8765** only from the GCP VM IP.

### 3. Ubuntu VM `.env`

```env
PPT_RENDER_BACKEND=remote
PPT_RENDER_REMOTE_URL=http://10.0.0.5:8765
PPT_RENDER_REMOTE_TOKEN=choose-a-long-random-secret
PPT_RENDER_REMOTE_TIMEOUT_SEC=300
```

```bash
sudo systemctl restart dsr-wsr-api
curl -s http://127.0.0.1:8000/health
# {"status":"ok","slide_renderer":"remote"}
```

### 4. Smoke test from VM

```bash
cd ~/DSR-WSR-AUTOMATION/DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation
source .venv/bin/activate
python - <<'PY'
from pathlib import Path
from app.rendering.factory import get_slide_renderer_backend
ppt = next(Path("output").glob("WSR_*.pptx"), None) or next(Path(".").rglob("*.pptx"))
out = Path("/tmp/preview_test")
out.mkdir(exist_ok=True)
paths = get_slide_renderer_backend().render_slides(ppt, out, width_px=1280)
print(len(paths), "slides ->", out)
PY
```

---

## Local Windows (no Ubuntu)

```env
PPT_RENDER_BACKEND=auto
```

Or `PPT_RENDER_BACKEND=com`. Requires PowerPoint + `pywin32` (already in requirements on Windows).

---

## LibreOffice (fallback only)

Acceptable for quick checks; **not** for client-facing template previews.

```bash
sudo apt install -y libreoffice-impress poppler-utils ttf-mscorefonts-installer
```

Embed fonts in templates (PowerPoint → File → Options → Save → *Embed fonts in the file*).

```env
PPT_RENDER_BACKEND=libreoffice
```

---

## Other commercial options (not built-in)

| Product | Notes |
|---------|--------|
| [Aspose.Slides for Python](https://products.aspose.com/slides/python-net/) | High fidelity on Linux, no PowerPoint; paid license |
| CloudConvert / similar APIs | Per-conversion cost, variable quality |
| Microsoft 365 Graph | Complex; not ideal for batch slide PNG export |

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `PPT_RENDER_BACKEND` | `auto`, `com`, `remote`, `libreoffice` |
| `PPT_RENDER_REMOTE_URL` | Base URL of Windows render server |
| `PPT_RENDER_REMOTE_TOKEN` | Bearer token (must match `PPT_RENDER_SERVER_TOKEN` on Windows) |
| `PPT_RENDER_REMOTE_TIMEOUT_SEC` | HTTP timeout (default 300) |
| `PPT_RENDER_SERVER_TOKEN` | Windows server auth token |
| `PPT_RENDER_SERVER_HOST` | Windows server bind (default `0.0.0.0`) |
| `PPT_RENDER_SERVER_PORT` | Windows server port (default `8765`) |
