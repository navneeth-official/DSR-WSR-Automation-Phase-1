"""Default dependency wiring for the vision layout pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.geometry.corrector import GeometryCorrector
from app.geometry.inspector import GeometryInspector
from app.pipeline.deck_generator import SubprocessDeckGenerator
from app.pipeline.hybrid_validation_loop import HybridValidationLoop
from app.pipeline.layout_corrector import (
    LegacyRepairLayoutCorrector,
    NullLayoutCorrector,
    VisionDrivenLayoutCorrector,
)
from app.pipeline.ppt_renderer import SlideImagePptRenderer
from app.pipeline.protocols import (
    DeckGenerator,
    LayoutCorrector,
    PptRenderer,
    ValidationLoop,
    VisionClient,
)
from app.pipeline.qualitative_reviewer import QualitativeVisionReviewer
from app.pipeline.types import PipelineMode
from app.pipeline.validation_loop import IterativeValidationLoop
from app.pipeline.vision_client import VisionLayoutInspectorClient


@dataclass
class PipelineDependencies:
    """Injectable collaborators for generate → validate → correct flows."""

    deck_generator: DeckGenerator
    renderer: PptRenderer
    vision_client: VisionClient
    corrector: LayoutCorrector
    validation_loop: ValidationLoop
    geometry_inspector: GeometryInspector
    geometry_corrector: GeometryCorrector
    qualitative_reviewer: QualitativeVisionReviewer
    hybrid_validation_loop: HybridValidationLoop
    pipeline_mode: PipelineMode = PipelineMode.HYBRID

    @classmethod
    def create_default(
        cls,
        *,
        layout_hints: Path | None = None,
        use_legacy_corrector: bool = False,
        use_vision_corrector: bool = True,
        legacy_max_rounds: int = 1,
        rulebook_path: Path | None = None,
        pipeline_mode: PipelineMode | str = PipelineMode.HYBRID,
    ) -> PipelineDependencies:
        """
        Build the default production wiring.

        Parameters
        ----------
        pipeline_mode:
            ``hybrid`` (default) — geometry inspect/correct + qualitative vision.
            ``legacy_vision_measurement`` — original pixel-measurement vision loop.
        use_legacy_corrector:
            When True, route corrections through the existing rulebook repair
            loop instead of the vision-driven corrector (legacy mode only).
        """
        del layout_hints

        if isinstance(pipeline_mode, str):
            pipeline_mode = PipelineMode(pipeline_mode)

        deck_generator = SubprocessDeckGenerator()
        renderer = SlideImagePptRenderer()
        vision_client = VisionLayoutInspectorClient(rulebook_path=rulebook_path)
        geometry_inspector = GeometryInspector()
        geometry_corrector = GeometryCorrector()
        qualitative_reviewer = QualitativeVisionReviewer()

        if use_legacy_corrector:
            corrector: LayoutCorrector = LegacyRepairLayoutCorrector(
                max_rounds=legacy_max_rounds,
            )
        elif use_vision_corrector:
            corrector = VisionDrivenLayoutCorrector()
        else:
            corrector = NullLayoutCorrector()

        legacy_loop = IterativeValidationLoop(
            renderer=renderer,
            vision_client=vision_client,
            corrector=corrector,
            deck_generator=deck_generator,
        )

        hybrid_loop = HybridValidationLoop(
            renderer=renderer,
            qualitative_reviewer=qualitative_reviewer,
            geometry_inspector=geometry_inspector,
            geometry_corrector=geometry_corrector,
            deck_generator=deck_generator,
        )

        active_loop: ValidationLoop = (
            hybrid_loop if pipeline_mode == PipelineMode.HYBRID else legacy_loop
        )

        return cls(
            deck_generator=deck_generator,
            renderer=renderer,
            vision_client=vision_client,
            corrector=corrector,
            validation_loop=active_loop,
            geometry_inspector=geometry_inspector,
            geometry_corrector=geometry_corrector,
            qualitative_reviewer=qualitative_reviewer,
            hybrid_validation_loop=hybrid_loop,
            pipeline_mode=pipeline_mode,
        )
