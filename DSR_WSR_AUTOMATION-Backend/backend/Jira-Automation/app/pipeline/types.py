"""Shared value types for the vision-based layout pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RenderedSlide:
    """One delivery-status slide exported to a raster image."""

    slide_index: int
    title: str
    image_path: Path


@dataclass
class RenderBatch:
    """PNG exports for a deck inspection pass."""

    ppt_path: Path
    output_dir: Path
    slides: list[RenderedSlide] = field(default_factory=list)

    def to_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "slide_index": s.slide_index,
                "title": s.title,
                "image_path": str(s.image_path),
            }
            for s in self.slides
        ]


@dataclass
class VisionReport:
    """Layout inspection output from a vision client."""

    deck_pass: bool
    deck_score: int
    slides: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    critical_issues: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisionReport:
        return cls(
            deck_pass=bool(data.get("deck_pass")),
            deck_score=int(data.get("deck_score") or 0),
            slides=list(data.get("slides") or []),
            summary=str(data.get("summary") or ""),
            critical_issues=list(data.get("critical_issues") or []),
            raw=data,
        )


@dataclass
class CorrectionResult:
    """Result of one layout-correction pass on the PPTX."""

    modified: bool
    ppt_path: Path
    actions_applied: list[str] = field(default_factory=list)
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    change_magnitude_emu: int = 0


@dataclass
class LoopIteration:
    """One render → evaluate → (optional) correct cycle."""

    iteration: int
    render_batch: RenderBatch
    vision_report: VisionReport
    correction: CorrectionResult | None = None


@dataclass
class ValidationLoopResult:
    """Outcome of the iterative validation loop."""

    ppt_path: Path
    passed: bool
    iterations: list[LoopIteration] = field(default_factory=list)
    final_report: VisionReport | None = None
    stopped_reason: str = ""

    @property
    def final_presentation(self) -> Path:
        """Path to the final ``.pptx`` after all iterations."""
        return self.ppt_path

    @property
    def final_validation_report(self) -> VisionReport | None:
        """Vision evaluation from the last render pass."""
        return self.final_report

    @property
    def iteration_history(self) -> list[LoopIteration]:
        """Ordered record of every render → evaluate → (optional) correct cycle."""
        return self.iterations

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_presentation": str(self.ppt_path),
            "passed": self.passed,
            "stopped_reason": self.stopped_reason,
            "iteration_count": len(self.iterations),
            "final_validation_report": self.final_report.raw if self.final_report else None,
            "iteration_history": [
                {
                    "iteration": it.iteration,
                    "rendered_slides": it.render_batch.to_metadata(),
                    "deck_pass": it.vision_report.deck_pass,
                    "deck_score": it.vision_report.deck_score,
                    "issue_count": sum(
                        len(s.get("issues") or []) for s in it.vision_report.slides
                    ),
                    "correction": {
                        "modified": it.correction.modified,
                        "actions_applied": it.correction.actions_applied,
                        "change_magnitude_emu": it.correction.change_magnitude_emu,
                        "message": it.correction.message,
                    }
                    if it.correction
                    else None,
                }
                for it in self.iterations
            ],
        }


@dataclass
class PipelineConfig:
    """Tunable parameters for the validation loop."""

    max_iterations: int = 3
    keep_render_images: bool = False
    render_output_dir: Path | None = None
    pass_threshold: int | None = None  # reserved for future scoring policies
    negligible_change_emu: int = 4572  # ~0.005 in — corrections below this stop the loop


class PipelineMode(str, Enum):
    """Pipeline inspection strategy."""

    HYBRID = "hybrid"
    LEGACY_VISION_MEASUREMENT = "legacy_vision_measurement"


@dataclass
class HybridLoopIteration:
    """One hybrid cycle: geometry inspect → correct → render → qualitative review."""

    iteration: int
    geometry_report: dict[str, Any] = field(default_factory=dict)
    geometry_correction: dict[str, Any] | None = None
    render_batch: dict[str, Any] = field(default_factory=dict)
    qualitative_report: dict[str, Any] = field(default_factory=dict)
    manual_review_slides: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class HybridValidationResult:
    """Outcome of the hybrid geometry + qualitative vision pipeline."""

    ppt_path: Path
    passed: bool
    stopped_reason: str = ""
    iterations: list[HybridLoopIteration] = field(default_factory=list)
    final_geometry_report: dict[str, Any] | None = None
    final_qualitative_report: dict[str, Any] | None = None
    manual_review_slides: list[dict[str, Any]] = field(default_factory=list)
    pipeline_mode: str = PipelineMode.HYBRID.value

    @property
    def final_presentation(self) -> Path:
        return self.ppt_path

    @property
    def iteration_history(self) -> list[HybridLoopIteration]:
        return self.iterations

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_mode": self.pipeline_mode,
            "final_presentation": str(self.ppt_path),
            "passed": self.passed,
            "stopped_reason": self.stopped_reason,
            "iteration_count": len(self.iterations),
            "final_geometry_report": self.final_geometry_report,
            "final_qualitative_report": self.final_qualitative_report,
            "manual_review_slides": self.manual_review_slides,
            "iteration_history": [
                {
                    "iteration": it.iteration,
                    "geometry_report": it.geometry_report,
                    "geometry_correction": it.geometry_correction,
                    "rendered_slides": it.render_batch,
                    "qualitative_report": it.qualitative_report,
                    "manual_review_slides": it.manual_review_slides,
                }
                for it in self.iterations
            ],
        }
