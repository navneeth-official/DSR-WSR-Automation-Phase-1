#!/usr/bin/env python3
"""
Windows PowerPoint COM render server (pixel-accurate slide PNG export).

Run on a Windows machine with Microsoft PowerPoint installed:

  cd DSR_WSR_AUTOMATION-Backend/backend/Jira-Automation
  .venv\\Scripts\\activate
  pip install pywin32 fastapi uvicorn python-multipart
  set PPT_RENDER_SERVER_TOKEN=your-secret-token
  python scripts/ppt_render_server.py

Ubuntu/GCP VM .env:

  PPT_RENDER_BACKEND=remote
  PPT_RENDER_REMOTE_URL=http://WINDOWS_HOST:8765
  PPT_RENDER_REMOTE_TOKEN=your-secret-token

Use a VPN, SSH tunnel, or private network — do not expose this service publicly
without authentication and firewall rules.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
import uvicorn

from app.rendering.com_backend import ComSlideRendererBackend

app = FastAPI(title="PPT COM Render Server", version="1.0.0")


def _check_token(authorization: str | None) -> None:
    expected = os.getenv("PPT_RENDER_SERVER_TOKEN", "").strip()
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "renderer": "com"}


@app.post("/render-slides")
async def render_slides(
    file: UploadFile = File(...),
    width_px: int = Form(1280),
    slide_indices: str | None = Form(None),
    authorization: str | None = Header(None, alias="Authorization"),
) -> Response:
    _check_token(authorization)

    if not file.filename or not file.filename.lower().endswith(".pptx"):
        raise HTTPException(status_code=400, detail="Upload a .pptx file")

    indices: list[int] | None = None
    if slide_indices:
        try:
            parsed = json.loads(slide_indices)
            if not isinstance(parsed, list):
                raise ValueError("slide_indices must be a JSON array")
            indices = [int(x) for x in parsed]
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid slide_indices: {exc}"
            ) from exc

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty upload")

    try:
        with tempfile.TemporaryDirectory(prefix="ppt_render_srv_") as tmp:
            work = Path(tmp)
            ppt_path = work / Path(file.filename).name
            ppt_path.write_bytes(payload)
            out_dir = work / "slides"
            out_dir.mkdir()

            backend = ComSlideRendererBackend()
            paths = backend.render_slides(
                ppt_path,
                out_dir,
                slide_indices=indices,
                width_px=width_px,
            )
            if not paths:
                raise HTTPException(status_code=422, detail="No slides exported")

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in paths:
                    zf.write(path, arcname=path.name)
            buffer.seek(0)
            return Response(
                content=buffer.read(),
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="slides.zip"'},
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def main() -> None:
    host = os.getenv("PPT_RENDER_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("PPT_RENDER_SERVER_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
