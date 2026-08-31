"""
Vision-based layout pipeline (modular architecture).

Stages
------
1. ``DeckGenerator`` — build PPTX via existing layout engine
2. ``PptRenderer`` — export slides to PNG
3. ``VisionClient`` — inspect rendered images
4. ``LayoutCorrector`` — apply deterministic fixes (stub / legacy bridge)
5. ``ValidationLoop`` — iterate until pass or max rounds

Use ``VisionLayoutPipeline`` as the high-level orchestrator, or inject
individual protocols via ``PipelineDependencies``.
"""

from app.pipeline.dependencies import PipelineDependencies
from app.pipeline.deck_generator import SubprocessDeckGenerator
from app.pipeline.hybrid_validation_loop import HybridValidationLoop
from app.pipeline.layout_corrector import (
    LegacyRepairLayoutCorrector,
    NullLayoutCorrector,
    VisionDrivenLayoutCorrector,
)
from app.pipeline.orchestrator import VisionLayoutPipeline
from app.pipeline.ppt_renderer import SlideImagePptRenderer
from app.pipeline.protocols import (
    DeckGenerator,
    LayoutCorrector,
    PptRenderer,
    ValidationLoop,
    VisionClient,
)
from app.pipeline.qualitative_reviewer import QualitativeVisionReviewer
from app.pipeline.types import (
    CorrectionResult,
    HybridLoopIteration,
    HybridValidationResult,
    LoopIteration,
    PipelineConfig,
    PipelineMode,
    RenderBatch,
    RenderedSlide,
    ValidationLoopResult,
    VisionReport,
)
from app.pipeline.validation_loop import IterativeValidationLoop
from app.pipeline.vision_client import VisionLayoutInspectorClient

__all__ = [
    "CorrectionResult",
    "DeckGenerator",
    "HybridLoopIteration",
    "HybridValidationLoop",
    "HybridValidationResult",
    "IterativeValidationLoop",
    "LayoutCorrector",
    "LegacyRepairLayoutCorrector",
    "LoopIteration",
    "NullLayoutCorrector",
    "PipelineConfig",
    "PipelineDependencies",
    "PipelineMode",
    "PptRenderer",
    "QualitativeVisionReviewer",
    "RenderBatch",
    "RenderedSlide",
    "SlideImagePptRenderer",
    "SubprocessDeckGenerator",
    "ValidationLoop",
    "ValidationLoopResult",
    "VisionClient",
    "VisionDrivenLayoutCorrector",
    "VisionLayoutInspectorClient",
    "VisionLayoutPipeline",
    "VisionReport",
]
