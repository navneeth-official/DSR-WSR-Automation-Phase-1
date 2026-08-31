"""Select slide renderer backend from settings / platform."""

from __future__ import annotations

import sys

from app.config import get_settings
from app.rendering.com_backend import ComSlideRendererBackend
from app.rendering.libreoffice_backend import LibreOfficeSlideRendererBackend
from app.rendering.protocol import SlideRendererBackend


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


def get_slide_renderer_backend() -> SlideRendererBackend:
    """
    Return the configured slide export backend.

    PPT_RENDER_BACKEND:
      - auto   — COM on Windows when pywin32 is present, else LibreOffice
      - com    — PowerPoint COM (Windows + installed PowerPoint)
      - libreoffice — headless LibreOffice + pdftoppm (cross-platform)
    """
    settings = get_settings()
    choice = (settings.ppt_render_backend or "auto").strip().lower()

    if choice == "auto":
        if com_backend_available():
            return ComSlideRendererBackend()
        if libreoffice_available(libreoffice_path=settings.libreoffice_path or None):
            return LibreOfficeSlideRendererBackend(
                libreoffice_path=settings.libreoffice_path or None,
                pdftoppm_path=settings.pdftoppm_path or None,
            )
        raise RuntimeError(
            "No slide renderer available. On Windows install PowerPoint + pywin32, "
            "or install LibreOffice and poppler-utils. On Linux install "
            "libreoffice-impress and poppler-utils, then set "
            "PPT_RENDER_BACKEND=libreoffice."
        )

    if choice in ("com", "powerpoint", "win32com"):
        return ComSlideRendererBackend()

    if choice in ("libreoffice", "lo"):
        return LibreOfficeSlideRendererBackend(
            libreoffice_path=settings.libreoffice_path or None,
            pdftoppm_path=settings.pdftoppm_path or None,
        )

    raise RuntimeError(
        f"Unknown PPT_RENDER_BACKEND={settings.ppt_render_backend!r}. "
        "Use auto, com, or libreoffice."
    )


def describe_active_renderer() -> str:
    """Human-readable label for logs and diagnostics."""
    settings = get_settings()
    choice = (settings.ppt_render_backend or "auto").strip().lower()
    if choice == "auto":
        if com_backend_available():
            return "com (auto)"
        if libreoffice_available(libreoffice_path=settings.libreoffice_path or None):
            return "libreoffice (auto)"
        return "none"
    return choice
