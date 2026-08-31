"""Typed results for qualitative vision layout review."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.constants.vision_qualitative_reviewer_prompt import (
    ALLOWED_QUALITATIVE_CATEGORIES,
    LEGACY_GEOMETRY_CATEGORIES,
    SLIDE_STATUS_NEEDS_REVIEW,
    SLIDE_STATUS_OK,
    VISUAL_SCORE_PASS_THRESHOLD,
)


class QualitativeCategory(str, Enum):
    POOR_VISUAL_BALANCE = "poor_visual_balance"
    EXCESSIVE_WHITESPACE = "excessive_whitespace"
    CRAMPED_LAYOUT = "cramped_layout"
    WEAK_HIERARCHY = "weak_hierarchy"
    OFF_TEMPLATE = "off_template"
    HL_OVERSIZED_FOR_CONTENT = "hl_oversized_for_content"
    PREMATURE_HL_CONTINUATION = "premature_hl_continuation"
    NO_ISSUE = "no_issue"

    @classmethod
    def from_raw(cls, value: str | None) -> QualitativeCategory | None:
        if value in ALLOWED_QUALITATIVE_CATEGORIES:
            return cls(value)  # type: ignore[arg-type]
        if value in LEGACY_GEOMETRY_CATEGORIES:
            return None
        return None


class ReviewStatus(str, Enum):
    OK = SLIDE_STATUS_OK
    NEEDS_REVIEW = SLIDE_STATUS_NEEDS_REVIEW


@dataclass(frozen=True)
class QualitativeIssue:
    category: QualitativeCategory
    severity: str
    confidence: float | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity,
            "confidence": self.confidence,
            "description": self.description,
        }


@dataclass(frozen=True)
class QualitativeSlideReview:
    slide_number: int | None
    status: ReviewStatus
    overall_quality: str
    issues: tuple[QualitativeIssue, ...] = ()
    visual_score: float | None = None
    category_scores: dict[str, float] = field(default_factory=dict)
    strengths: tuple[str, ...] = ()

    @property
    def passes(self) -> bool:
        if self.visual_score is not None and self.visual_score < VISUAL_SCORE_PASS_THRESHOLD:
            return False
        if self.status == ReviewStatus.OK:
            return True
        return not any(
            i.severity in ("high", "medium")
            for i in self.issues
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_number": self.slide_number,
            "status": self.status.value,
            "pass": self.passes,
            "overall_quality": self.overall_quality,
            "visual_score": self.visual_score,
            "category_scores": dict(self.category_scores),
            "issues": [i.to_dict() for i in self.issues],
            "strengths": list(self.strengths),
        }


@dataclass
class QualitativeReviewReport:
    deck_pass: bool
    slides: list[QualitativeSlideReview] = field(default_factory=list)
    summary: str = ""
    evaluator: str = "visual_quality_reviewer"
    vision_model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "deck_pass": self.deck_pass,
            "slides": [s.to_dict() for s in self.slides],
            "summary": self.summary,
            "evaluator": self.evaluator,
            "vision_model": self.vision_model,
        }
