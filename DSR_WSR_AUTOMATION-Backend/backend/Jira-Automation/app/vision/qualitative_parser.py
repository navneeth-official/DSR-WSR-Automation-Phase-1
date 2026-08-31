"""Parse qualitative vision JSON (subjective visual quality only)."""

from __future__ import annotations

from typing import Any

from app.vision.parser import extract_json_object
from app.vision.qualitative_types import (
    QualitativeCategory,
    QualitativeIssue,
    QualitativeSlideReview,
    ReviewStatus,
)


def _coerce_confidence(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _coerce_score(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 1)
    return None


def _parse_category_scores(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, val in raw.items():
        score = _coerce_score(val)
        if score is not None:
            out[str(key)] = score
    return out


def parse_qualitative_review(raw: dict[str, Any]) -> QualitativeSlideReview:
    issues_raw = raw.get("issues") or []
    issues: list[QualitativeIssue] = []
    if isinstance(issues_raw, list):
        for entry in issues_raw:
            if not isinstance(entry, dict):
                continue
            category = QualitativeCategory.from_raw(entry.get("category"))
            if category is None or category == QualitativeCategory.NO_ISSUE:
                continue
            issues.append(
                QualitativeIssue(
                    category=category,
                    severity=str(entry.get("severity") or "low"),
                    confidence=_coerce_confidence(entry.get("confidence")),
                    description=str(entry.get("description") or ""),
                )
            )

    slide_number_raw = raw.get("slide_number", raw.get("slide_index"))
    slide_number = (
        int(slide_number_raw) if isinstance(slide_number_raw, (int, float)) else None
    )

    status_raw = raw.get("status")
    if status_raw == ReviewStatus.OK.value and not issues:
        status = ReviewStatus.OK
    elif issues:
        status = ReviewStatus.NEEDS_REVIEW
    elif status_raw == ReviewStatus.NEEDS_REVIEW.value:
        status = ReviewStatus.NEEDS_REVIEW
    else:
        status = ReviewStatus.OK

    strengths_raw = raw.get("strengths") or []
    strengths = tuple(
        str(s) for s in strengths_raw if isinstance(s, str) and s.strip()
    )

    return QualitativeSlideReview(
        slide_number=slide_number,
        status=status,
        overall_quality=str(raw.get("overall_quality") or "acceptable"),
        issues=tuple(issues),
        visual_score=_coerce_score(raw.get("visual_score")),
        category_scores=_parse_category_scores(raw.get("category_scores")),
        strengths=strengths,
    )


def parse_qualitative_from_text(text: str) -> QualitativeSlideReview:
    return parse_qualitative_review(extract_json_object(text))
