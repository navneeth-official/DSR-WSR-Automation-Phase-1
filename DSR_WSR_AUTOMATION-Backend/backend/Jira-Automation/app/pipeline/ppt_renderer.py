"""Adapter: export PPTX slides to PNG via ``PowerPointRenderer``."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from app.pipeline.types import RenderBatch, RenderedSlide
from app.rendering import PowerPointRenderer
from app.services.ppt_slide_images import export_slides_to_png, list_delivery_slide_indices


class SlideImagePptRenderer:
    """
    Pipeline-facing ``PptRenderer`` implementation.

    Uses ``PowerPointRenderer`` for full-deck export when no slide filter is
    required; falls back to delivery-slide filtering via ``ppt_slide_images``.
    """

    def __init__(self, renderer: PowerPointRenderer | None = None) -> None:
        self._renderer = renderer

    def render_deck(
        self,
        ppt_path: Path,
        *,
        output_dir: Path | None = None,
        keep_images: bool = False,
        delivery_slides_only: bool = True,
    ) -> RenderBatch:
        ppt_path = ppt_path.resolve()
        temp_dir: Path | None = None

        if output_dir is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="ppt_pipeline_render_"))
            target_dir = temp_dir
        else:
            target_dir = Path(output_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

        if delivery_slides_only:
            slide_meta = list_delivery_slide_indices(ppt_path)
            exported_meta = export_slides_to_png(
                ppt_path,
                target_dir,
                slide_indices=[s["slide_index"] for s in slide_meta],
            )
        else:
            renderer = self._renderer or PowerPointRenderer(
                output_dir=target_dir,
            )
            image_paths = renderer.render(ppt_path)
            exported_meta = [
                {
                    "slide_index": int(p.stem.split("_", 1)[1]),
                    "title": "",
                    "image_path": str(p),
                }
                for p in image_paths
            ]

        slides = [
            RenderedSlide(
                slide_index=int(entry["slide_index"]),
                title=str(entry.get("title") or ""),
                image_path=Path(entry["image_path"]),
            )
            for entry in exported_meta
        ]

        batch = RenderBatch(
            ppt_path=ppt_path,
            output_dir=target_dir,
            slides=slides,
        )

        if temp_dir is not None and not keep_images:
            for slide in slides:
                slide.image_path.unlink(missing_ok=True)
            shutil.rmtree(temp_dir, ignore_errors=True)
            batch = RenderBatch(
                ppt_path=ppt_path,
                output_dir=ppt_path.parent,
                slides=slides,
            )

        return batch
