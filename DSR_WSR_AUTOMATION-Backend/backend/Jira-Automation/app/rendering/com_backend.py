"""PowerPoint COM backend for pixel-accurate slide export (Windows)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence
import shutil
import tempfile


@contextmanager
def _com_apartment() -> Iterator[None]:
    """Initialize COM on the current thread (required under FastAPI thread pools)."""
    import pythoncom  # type: ignore[import-untyped]

    initialized_here = False
    try:
        pythoncom.CoInitialize()
        initialized_here = True
    except pythoncom.com_error as exc:
        # Thread already has COM initialized (nested call or prior init).
        if getattr(exc, "hresult", None) not in (-2147417850, -2147221007):
            raise
    try:
        yield
    finally:
        if initialized_here:
            pythoncom.CoUninitialize()


class ComSlideRendererBackend:
    """
    Renders slides through the installed PowerPoint application.

    Uses ``Slide.Export`` so fonts, spacing, and shapes match the live deck.
    """

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

        try:
            import win32com.client  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "win32com is required for PowerPoint rendering. "
                "Install with: pip install pywin32"
            ) from exc

        with _com_apartment():
            app = win32com.client.Dispatch("PowerPoint.Application")
            _set_powerpoint_visible(app, visible=False)
            open_path = _local_copy_for_com(ppt_path)
            exported: list[Path] = []
            try:
                presentation = app.Presentations.Open(str(open_path), WithWindow=False)
                try:
                    slide_count = int(presentation.Slides.Count)
                    indices = (
                        list(slide_indices)
                        if slide_indices is not None
                        else list(range(1, slide_count + 1))
                    )

                    slide_width = float(presentation.PageSetup.SlideWidth)
                    slide_height = float(presentation.PageSetup.SlideHeight)
                    if slide_width <= 0:
                        slide_width = 720.0
                    height_px = max(1, int(width_px * slide_height / slide_width))

                    for idx in indices:
                        if idx < 1 or idx > slide_count:
                            continue
                        slide = presentation.Slides(idx)
                        out_path = (output_dir / f"slide_{idx:02d}.png").resolve()
                        slide.Export(str(out_path), "PNG", width_px, height_px)
                        exported.append(out_path)
                finally:
                    presentation.Close()
            finally:
                app.Quit()
                open_path.unlink(missing_ok=True)

        return exported


def _local_copy_for_com(ppt_path: Path) -> Path:
    """Copy to a temp path so PowerPoint COM can open OneDrive-synced files reliably."""
    temp_file = Path(tempfile.NamedTemporaryFile(suffix=".pptx", delete=False).name)
    shutil.copy2(ppt_path, temp_file)
    return temp_file


def _set_powerpoint_visible(app, *, visible: bool) -> None:
    """
    Set PowerPoint visibility; some installs forbid hiding the app window.

    Falls back to visible=True when ``Visible = False`` is rejected by COM.
    """
    try:
        app.Visible = -1 if visible else 0  # msoTrue / msoFalse
    except Exception:
        try:
            app.Visible = 1 if visible else 0
        except Exception:
            app.Visible = 1
