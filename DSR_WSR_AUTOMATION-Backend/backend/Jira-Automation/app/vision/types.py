"""Strongly typed vision evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.constants.vision_layout_inspector_prompt import (
    ALLOWED_VISION_RECOMMENDED_ACTIONS,
    SLIDE_STATUS_NEEDS_ADJUSTMENT,
    SLIDE_STATUS_OK,
)


class SlideStatus(str, Enum):
    OK = SLIDE_STATUS_OK
    NEEDS_ADJUSTMENT = SLIDE_STATUS_NEEDS_ADJUSTMENT


class RecommendedAction(str, Enum):
    INCREASE_TEXTBOX_HEIGHT = "increase_textbox_height"
    DECREASE_TEXTBOX_HEIGHT = "decrease_textbox_height"
    MOVE_SECTION_DOWN = "move_section_down"
    MOVE_SECTION_UP = "move_section_up"
    RESTORE_TEMPLATE_POSITION = "restore_template_position"
    REDUCE_UNUSED_SPACE = "reduce_unused_space"
    EXPAND_PLACEHOLDER = "expand_placeholder"
    OVERFLOW_DETECTED = "overflow_detected"
    NO_ACTION = "no_action"

    @classmethod
    def from_raw(cls, value: str | None) -> RecommendedAction:
        if value in ALLOWED_VISION_RECOMMENDED_ACTIONS:
            return cls(value)  # type: ignore[arg-type]
        return cls.NO_ACTION


@dataclass(frozen=True)
class SlideMeasurements:
    """Pixel measurements reported by the vision model."""

    values: dict[str, int | float] = field(default_factory=dict)

    def get(self, key: str, default: int | float | None = None) -> int | float | None:
        return self.values.get(key, default)

    @property
    def gap_between_sections(self) -> int | float | None:
        return self.values.get("gap_between_sections")

    @property
    def unused_space_inside_highlight(self) -> int | float | None:
        return self.values.get("unused_space_inside_highlight")

    @property
    def highlight_box_top(self) -> int | float | None:
        return self.values.get("highlight_box_top")

    @property
    def highlight_box_bottom(self) -> int | float | None:
        return self.values.get("highlight_box_bottom")

    @property
    def last_highlight_text_bottom(self) -> int | float | None:
        return self.values.get("last_highlight_text_bottom")

    @property
    def keyactivities_title_top(self) -> int | float | None:
        return self.values.get("keyactivities_title_top")

    @property
    def keyactivities_box_top(self) -> int | float | None:
        return self.values.get("keyactivities_box_top")

    @property
    def keyactivities_box_bottom(self) -> int | float | None:
        return self.values.get("keyactivities_box_bottom")


@dataclass(frozen=True)
class LayoutIssue:
    issue_id: str
    severity: str
    confidence: float | None
    affected_object: str
    measurement: dict[str, int | float]
    explanation: str
    recommended_action: RecommendedAction


@dataclass(frozen=True)
class SlideEvaluationResult:
    """Parsed layout evaluation for a single rendered slide image."""

    slide_number: int | None
    status: SlideStatus
    measurements: SlideMeasurements
    issues: tuple[LayoutIssue, ...] = ()
    visual_notes: str = ""

    @property
    def passes(self) -> bool:
        if self.status != SlideStatus.OK:
            return False
        return not any(issue.severity == "high" for issue in self.issues)

    @property
    def score(self) -> int:
        if self.passes:
            return 100
        high_count = sum(1 for issue in self.issues if issue.severity == "high")
        return max(0, 100 - 25 * len(self.issues) - 15 * high_count)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging or legacy consumers."""
        return {
            "slide_number": self.slide_number,
            "status": self.status.value,
            "pass": self.passes,
            "score": self.score,
            "measurements": dict(self.measurements.values),
            "issues": [
                {
                    "issue_id": issue.issue_id,
                    "severity": issue.severity,
                    "confidence": issue.confidence,
                    "affected_object": issue.affected_object,
                    "measurement": dict(issue.measurement),
                    "explanation": issue.explanation,
                    "recommended_action": issue.recommended_action.value,
                }
                for issue in self.issues
            ],
            "violations": [
                {
                    "rule_id": issue.issue_id,
                    "severity": issue.severity,
                    "message": issue.explanation,
                    "recommended_action": issue.recommended_action.value,
                }
                for issue in self.issues
            ],
            "visual_notes": self.visual_notes,
        }
