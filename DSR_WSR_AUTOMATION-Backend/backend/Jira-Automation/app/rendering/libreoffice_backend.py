"""LibreOffice + Poppler backend for slide export (Linux/macOS/Windows)."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from pptx import Presentation

# Typical 16:9 Impress slide width in inches (254 mm).
_DEFAULT_SLIDE_WIDTH_IN = 10.0


class LibreOfficeSlideRendererBackend:
    """
    Renders slides via headless LibreOffice (PPTX → PDF) and pdftoppm (PDF → PNG).

    Requires ``libreoffice`` (or ``soffice``) and ``pdftoppm`` (poppler-utils).
    """

    def __init__(
        self,
        *,
        libreoffice_path: str | None = None,
        pdftoppm_path: str | None = None,
        convert_timeout_sec: int = 300,
    ) -> None:
        self._libreoffice_path = libreoffice_path
        self._pdftoppm_path = pdftoppm_path
        self._convert_timeout_sec = convert_timeout_sec

    def render_slides(
        self,
        ppt_path: Path,
        output_dir: Path,
        *,
        slide_indices: Sequence[int] | None = None,
        width_px: int = 1920,
    ) -> list[Path]:
        ppt_path = ppt_path.resolve()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        slide_count = len(Presentation(str(ppt_path)).slides)
        indices = (
            list(slide_indices)
            if slide_indices is not None
            else list(range(1, slide_count + 1))
        )
        indices = [idx for idx in indices if 1 <= idx <= slide_count]
        if not indices:
            return []

        soffice = _resolve_soffice(self._libreoffice_path)
        pdftoppm = _resolve_pdftoppm(self._pdftoppm_path)

        with tempfile.TemporaryDirectory(prefix="ppt_lo_render_") as tmp:
            work_dir = Path(tmp)
            profile_dir = work_dir / "lo_profile"
            profile_dir.mkdir()
            pdf_path = _convert_pptx_to_pdf(
                soffice=soffice,
                ppt_path=ppt_path,
                work_dir=work_dir,
                profile_dir=profile_dir,
                timeout_sec=self._convert_timeout_sec,
            )
            page_pngs = _pdf_pages_to_png(
                pdftoppm=pdftoppm,
                pdf_path=pdf_path,
                work_dir=work_dir,
                width_px=width_px,
                timeout_sec=self._convert_timeout_sec,
            )

        exported: list[Path] = []
        for idx in indices:
            page_png = _page_png_for_slide_index(page_pngs, idx)
            if page_png is None:
                continue
            out_path = (output_dir / f"slide_{idx:02d}.png").resolve()
            shutil.copy2(page_png, out_path)
            exported.append(out_path)
        return exported


def _resolve_soffice(explicit: str | None) -> str:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return str(path)
        found = shutil.which(explicit)
        if found:
            return found
        raise RuntimeError(
            f"LIBREOFFICE_PATH is set but not found: {explicit!r}. "
            "Install LibreOffice or fix the path."
        )
    for candidate in ("libreoffice", "soffice"):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError(
        "LibreOffice not found. Install it (e.g. apt install libreoffice-impress) "
        "or set LIBREOFFICE_PATH."
    )


def _resolve_pdftoppm(explicit: str | None) -> str:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return str(path)
        found = shutil.which(explicit)
        if found:
            return found
        raise RuntimeError(
            f"PDFTOPPM_PATH is set but not found: {explicit!r}. "
            "Install poppler-utils or fix the path."
        )
    found = shutil.which("pdftoppm")
    if found:
        return found
    raise RuntimeError(
        "pdftoppm not found. Install poppler-utils (e.g. apt install poppler-utils)."
    )


def _convert_pptx_to_pdf(
    *,
    soffice: str,
    ppt_path: Path,
    work_dir: Path,
    profile_dir: Path,
    timeout_sec: int,
) -> Path:
    user_install = profile_dir.resolve().as_uri()
    cmd = [
        soffice,
        f"-env:UserInstallation={user_install}",
        "--headless",
        "--norestore",
        "--nologo",
        "--convert-to",
        "pdf",
        "--outdir",
        str(work_dir),
        str(ppt_path),
    ]
    _run(cmd, timeout_sec=timeout_sec, label="LibreOffice PDF conversion")

    pdf_candidates = sorted(work_dir.glob("*.pdf"))
    if not pdf_candidates:
        raise RuntimeError(
            f"LibreOffice did not produce a PDF for {ppt_path.name}. "
            "Check LibreOffice logs and file permissions."
        )
    return pdf_candidates[0]


def _pdf_pages_to_png(
    *,
    pdftoppm: str,
    pdf_path: Path,
    work_dir: Path,
    width_px: int,
    timeout_sec: int,
) -> list[Path]:
    prefix = work_dir / "page"
    cmd = [
        pdftoppm,
        "-png",
        "-scale-to-x",
        str(max(1, width_px)),
        str(pdf_path),
        str(prefix),
    ]
    try:
        _run(cmd, timeout_sec=timeout_sec, label="pdftoppm PNG export")
    except RuntimeError:
        # Older poppler may lack -scale-to-x; fall back to DPI from slide width.
        dpi = max(72, int(width_px / _DEFAULT_SLIDE_WIDTH_IN))
        cmd = [
            pdftoppm,
            "-png",
            "-rx",
            str(dpi),
            "-ry",
            str(dpi),
            str(pdf_path),
            str(prefix),
        ]
        _run(cmd, timeout_sec=timeout_sec, label="pdftoppm PNG export (dpi fallback)")

    pages = sorted(work_dir.glob("page-*.png"), key=_page_number_sort_key)
    if not pages:
        raise RuntimeError(f"pdftoppm did not produce PNG pages for {pdf_path.name}")
    return pages


def _page_number_sort_key(path: Path) -> int:
    match = re.search(r"-(\d+)\.png$", path.name, re.I)
    return int(match.group(1)) if match else 0


def _page_png_for_slide_index(page_pngs: list[Path], slide_index: int) -> Path | None:
    """Map 1-based slide index to pdftoppm page file (also 1-based)."""
    if slide_index < 1 or slide_index > len(page_pngs):
        return None
    return page_pngs[slide_index - 1]


def _run(cmd: list[str], *, timeout_sec: int, label: str) -> None:
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{label} timed out after {timeout_sec}s") from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(f"{label} failed: {detail}")
