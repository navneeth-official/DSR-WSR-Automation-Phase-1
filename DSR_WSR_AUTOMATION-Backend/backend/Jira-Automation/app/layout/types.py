"""Value types for layout correction."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.vision.types import SlideEvaluationResult


class CorrectionActionType(str, Enum):
    MOVE_SHAPE = "move_shape"
    RESIZE_SHAPE = "resize_shape"
    RESTORE_TEMPLATE = "restore_template_position"
    MAINTAIN_GAP = "maintain_gap"
    MAINTAIN_ALIGNMENT = "maintain_alignment"
    LAYOUT_FAILURE = "layout_failure"


@dataclass(frozen=True)
class CorrectionAction:
    action_type: CorrectionActionType
    target: str
    detail: str
    delta_emu: int | None = None


@dataclass(frozen=True)
class SlideCorrectionInput:
    """Vision evaluation plus optional rendered image for pixel scaling."""

    evaluation: SlideEvaluationResult
    image_path: Path | None = None


@dataclass
class SlideCorrectionResult:
    slide_number: int | None
    modified: bool = False
    actions: list[CorrectionAction] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.failures


@dataclass
class LayoutCorrectionResult:
    ppt_path: Path
    modified: bool
    slides: list[SlideCorrectionResult] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def actions_applied(self) -> list[str]:
        return [
            f"{a.action_type.value}:{a.target}"
            for s in self.slides
            for a in s.actions
        ]

    @property
    def change_magnitude_emu(self) -> int:
        total = 0
        for slide in self.slides:
            for action in slide.actions:
                if action.delta_emu is not None:
                    total += abs(action.delta_emu)
        return total

    def to_correction_result(self) -> Any:
        """Convert to pipeline ``CorrectionResult``."""
        from app.pipeline.types import CorrectionResult

        return CorrectionResult(
            modified=self.modified,
            ppt_path=self.ppt_path,
            actions_applied=self.actions_applied,
            change_magnitude_emu=self.change_magnitude_emu,
            message=(
                f"Applied {len(self.actions_applied)} layout action(s)"
                if self.modified
                else "No layout changes applied"
            ),
            details={
                "failures": self.failures,
                "change_magnitude_emu": self.change_magnitude_emu,
                "slides": [
                    {
                        "slide_number": s.slide_number,
                        "modified": s.modified,
                        "actions": [a.detail for a in s.actions],
                        "deltas_emu": [
                            action.delta_emu
                            for action in s.actions
                            if action.delta_emu is not None
                        ],
                        "failures": s.failures,
                    }
                    for s in self.slides
                ],
            },
        )
