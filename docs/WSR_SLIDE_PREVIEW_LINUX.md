# WSR slide preview on Linux (Ubuntu)

WSR slide previews are PNG images generated from the `.pptx` after deck creation. The backend supports two renderers:

| `PPT_RENDER_BACKEND` | Platform | Requirements |
|----------------------|----------|----------------|
| `auto` (default) | Windows | PowerPoint + pywin32 |
| `auto` (default) | Linux | LibreOffice + poppler-utils |
| `com` | Windows | PowerPoint + pywin32 |
| `libreoffice` | Any | LibreOffice + poppler-utils |

## Ubuntu VM setup

```bash
sudo apt update
sudo apt install -y libreoffice-impress poppler-utils
which libreoffice pdftoppm
```

Add to backend `.env` on the VM:

```env
PPT_RENDER_BACKEND=libreoffice
```

Or leave `PPT_RENDER_BACKEND=auto` — on Linux, `auto` selects LibreOffice when installed.

Restart the API:

```bash
sudo systemctl restart dsr-wsr-api
curl -s http://127.0.0.1:8000/health
# {"status":"ok","slide_renderer":"libreoffice (auto)"}
```

## Manual smoke test

```bash
cd ~/DSR-WSR-AUTOMATION/DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation
source .venv/bin/activate
python - <<'PY'
from pathlib import Path
from app.rendering.factory import get_slide_renderer_backend

ppt = next(Path("output").glob("WSR_*.pptx"), None)
if not ppt:
    raise SystemExit("No WSR pptx in output/ — generate one first")
out = ppt.parent / f"{ppt.stem}_test_slides"
backend = get_slide_renderer_backend()
paths = backend.render_slides(ppt, out, width_px=1280)
print(f"Exported {len(paths)} slides to {out}")
PY
```

## Notes

- Rendering uses **LibreOffice headless** (PPTX → PDF) and **pdftoppm** (PDF → PNG). Layout may differ slightly from PowerPoint on Windows; fonts should be installed on the VM for best fidelity.
- COM-specific tools (`ppt_hl_bounds_debug`, COM text bounds) remain Windows-only; WSR **UI previews** work on Ubuntu with LibreOffice.
- Optional overrides: `LIBREOFFICE_PATH`, `PDFTOPPM_PATH`.
