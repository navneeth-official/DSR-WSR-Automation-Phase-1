"""Select slide renderer backend from settings / platform."""

from __future__ import annotations

import sys

from app.config import get_settings
from app.rendering.com_backend import ComSlideRendererBackend
from app.rendering.libreoffice_backend import LibreOfficeSlideRendererBackend
from app.rendering.protocol import SlideRendererBackend
from app.rendering.remote_backend import RemoteSlideRendererBackend


def libreoffice_available(*, libreoffice_path: str | None = None) -> bool:
    """True when LibreOffice and pdftoppm are available."""
    try:
        from app.rendering.libreoffice_backend import (
            _resolve_pdftoppm,
            _resolve_soffice,
        )

        _resolve_soffice(libreoffice_path)
        _resolve_pdftoppm(None)
        return True
    except RuntimeError:
        return False


def com_backend_available() -> bool:
    """True when pywin32 is importable (Windows COM path)."""
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    return True


def remote_backend_configured() -> bool:
    settings = get_settings()
    return bool((settings.ppt_render_remote_url or "").strip())


def get_slide_renderer_backend() -> SlideRendererBackend:
    """
    Return the configured slide export backend.

    PPT_RENDER_BACKEND:
      - auto   — COM on Windows; remote URL on Linux if set; else LibreOffice
      - com    — PowerPoint COM (Windows + installed PowerPoint)
      - remote — Windows COM render service (pixel-perfect from Linux VM)
      - libreoffice — headless LibreOffice (lower fidelity)
    """
    settings = get_settings()
    choice = (settings.ppt_render_backend or "auto").strip().lower()

    if choice == "auto":
        if com_backend_available():
            return ComSlideRendererBackend()
        if remote_backend_configured():
            return _remote_backend(settings)
        if libreoffice_available(libreoffice_path=settings.libreoffice_path or None):
            return LibreOfficeSlideRendererBackend(
                libreoffice_path=settings.libreoffice_path or None,
                pdftoppm_path=settings.pdftoppm_path or None,
            )
        raise RuntimeError(
            "No slide renderer available. For production previews on Linux, set "
            "PPT_RENDER_BACKEND=remote and PPT_RENDER_REMOTE_URL to a Windows "
            "machine running scripts/ppt_render_server.py (see docs/WSR_SLIDE_PREVIEW.md). "
            "Fallback: install LibreOffice + poppler-utils and set "
            "PPT_RENDER_BACKEND=libreoffice (lower fidelity)."
        )

    if choice in ("com", "powerpoint", "win32com"):
        return ComSlideRendererBackend()

    if choice == "remote":
        if not remote_backend_configured():
            raise RuntimeError(
                "PPT_RENDER_BACKEND=remote requires PPT_RENDER_REMOTE_URL "
                "(Windows COM render server). See docs/WSR_SLIDE_PREVIEW.md."
            )
        return _remote_backend(settings)

    if choice in ("libreoffice", "lo"):
        return LibreOfficeSlideRendererBackend(
            libreoffice_path=settings.libreoffice_path or None,
            pdftoppm_path=settings.pdftoppm_path or None,
        )

    raise RuntimeError(
        f"Unknown PPT_RENDER_BACKEND={settings.ppt_render_backend!r}. "
        "Use auto, com, remote, or libreoffice."
    )


def _remote_backend(settings) -> RemoteSlideRendererBackend:
    return RemoteSlideRendererBackend(
        base_url=settings.ppt_render_remote_url.strip(),
        token=(settings.ppt_render_remote_token or None) or None,
        timeout_sec=settings.ppt_render_remote_timeout_sec,
    )


def describe_active_renderer() -> str:
    """Human-readable label for logs and diagnostics."""
    settings = get_settings()
    choice = (settings.ppt_render_backend or "auto").strip().lower()
    if choice == "auto":
        if com_backend_available():
            return "com (auto)"
        if remote_backend_configured():
            return "remote (auto)"
        if libreoffice_available(libreoffice_path=settings.libreoffice_path or None):
            return "libreoffice (auto)"
        return "none"
    if choice == "remote" and settings.ppt_render_remote_url:
        return f"remote ({settings.ppt_render_remote_url})"
    return choice
