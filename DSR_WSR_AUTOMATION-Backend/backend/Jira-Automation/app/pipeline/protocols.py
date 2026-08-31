"""Abstract interfaces for the vision-based layout pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.pipeline.types import (
    CorrectionResult,
    PipelineConfig,
    RenderBatch,
    ValidationLoopResult,
    VisionReport,
)


@runtime_checkable
class DeckGenerator(Protocol):
    """Builds or rebuilds a PPTX from structured content JSON."""

    def generate(
        self,
        content_json: Path,
        output_ppt: Path,
        *,
        layout_hints: Path | None = None,
    ) -> Path:
        """Run the existing layout engine and return the output PPTX path."""
        ...


@runtime_checkable
class PptRenderer(Protocol):
    """Exports rendered slide images from a PPTX."""

    def render_deck(
        self,
        ppt_path: Path,
        *,
        output_dir: Path | None = None,
        keep_images: bool = False,
    ) -> RenderBatch:
        """Export delivery-status slides to PNG for visual inspection."""
        ...


@runtime_checkable
class VisionClient(Protocol):
    """Inspects rendered slide images and returns layout measurements."""

    def evaluate(self, render_batch: RenderBatch) -> VisionReport:
        """Produce a structured vision report for the rendered slides."""
        ...

    def passes(self, report: VisionReport) -> bool:
        """Return True when the deck satisfies the vision validation policy."""
        ...


@runtime_checkable
class LayoutCorrector(Protocol):
    """Applies deterministic layout fixes to a PPTX based on a vision report."""

    def correct(
        self,
        ppt_path: Path,
        report: VisionReport,
        *,
        content_json: Path | None = None,
    ) -> CorrectionResult:
        """Modify the deck in place or via rebuild; return whether anything changed."""
        ...


@runtime_checkable
class ValidationLoop(Protocol):
    """Iterative render → evaluate → correct cycle."""

    def run(
        self,
        ppt_path: Path | None = None,
        *,
        content_json: Path | None = None,
        output_ppt: Path | None = None,
        layout_hints: Path | None = None,
        config: PipelineConfig | None = None,
    ) -> ValidationLoopResult:
        """Repeat until layout passes or termination criteria are met."""
        ...
