"""Abstract interface for PowerPoint slide rendering backends."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable


@runtime_checkable
class SlideRendererBackend(Protocol):
    """
    Low-level slide export backend.

    Implementations must render slides individually and preserve the
    on-slide layout as PowerPoint would display it.
    """

    def render_slides(
        self,
        ppt_path: Path,
        output_dir: Path,
        *,
        slide_indices: Sequence[int] | None = None,
        width_px: int = 1920,
    ) -> list[Path]:
        """
        Export slides to PNG files.

        When ``slide_indices`` is omitted, every slide in the deck is exported.
        Returns image paths in ascending slide-index order.
        """
        ...
