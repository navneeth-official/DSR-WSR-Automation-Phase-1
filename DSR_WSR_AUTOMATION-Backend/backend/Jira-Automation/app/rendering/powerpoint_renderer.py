"""High-level PowerPoint-to-PNG renderer."""

from __future__ import annotations

from pathlib import Path

from app.rendering.com_backend import ComSlideRendererBackend
from app.rendering.protocol import SlideRendererBackend


class PowerPointRenderer:
    """
    Export every slide in a ``.pptx`` deck to individual PNG images.

    This module is independent of the layout engine and vision pipeline.
    Inject a different ``SlideRendererBackend`` to swap rendering technology
    (for example LibreOffice, cloud API, or a mock for tests).
    """

    def __init__(
        self,
        *,
        output_dir: Path | str | None = None,
        width_px: int = 1920,
        backend: SlideRendererBackend | None = None,
    ) -> None:
        self._output_dir = Path(output_dir) if output_dir is not None else None
        self._width_px = width_px
        self._backend: SlideRendererBackend = backend or ComSlideRendererBackend()

    @property
    def output_dir(self) -> Path | None:
        return self._output_dir

    @property
    def width_px(self) -> int:
        return self._width_px

    def render(self, ppt_path: Path | str) -> list[Path]:
        """
        Render all slides in ``ppt_path`` to PNG files.

        Returns an ordered list of image paths (one per slide, ascending index).
        """
        ppt_path = Path(ppt_path).resolve()
        if not ppt_path.is_file():
            raise FileNotFoundError(f"PowerPoint file not found: {ppt_path}")

        target_dir = self._resolve_output_dir(ppt_path)
        return self._backend.render_slides(
            ppt_path,
            target_dir,
            slide_indices=None,
            width_px=self._width_px,
        )

    def _resolve_output_dir(self, ppt_path: Path) -> Path:
        if self._output_dir is not None:
            target = self._output_dir
        else:
            target = ppt_path.parent / f"{ppt_path.stem}_render"
        target.mkdir(parents=True, exist_ok=True)
        return target
