"""Visual quality scoring from qualitative AI review (subjective only)."""

from __future__ import annotations

from typing import Any

from app.vision.qualitative_types import QualitativeCategory, QualitativeSlideReview

VISUAL_PASS_THRESHOLD = 70.0
VISUAL_CATEGORY_WEIGHTS: dict[str, float] = {
    "visual_balance": 0.25,
    "readability": 0.25,
    "space_utilization": 0.20,
    "whitespace_quality": 0.20,  # legacy alias from model output
    "presentation_quality": 0.30,
}

_ISSUE_DEDUCTIONS: dict[str, int] = {
    "high": 25,
    "medium": 15,
    "low": 8,
}

_QUALITY_BASE: dict[str, float] = {
    "good": 92.0,
    "acceptable": 78.0,
    "poor": 55.0,
}


def _score_from_issues(review: QualitativeSlideReview) -> float:
    base = _QUALITY_BASE.get(review.overall_quality.lower(), 78.0)
    for issue in review.issues:
        if issue.category == QualitativeCategory.NO_ISSUE:
            continue
        base -= float(_ISSUE_DEDUCTIONS.get(issue.severity.lower(), 10))
    return round(max(0.0, min(100.0, base)), 1)


def _default_category_scores(visual_score: float) -> dict[str, float]:
    return {
        category: round(visual_score, 1)
        for category in (
            "visual_balance",
            "readability",
            "space_utilization",
            "presentation_quality",
        )
    }


def _normalize_category_scores(
    category_scores: dict[str, float],
    visual_score: float,
) -> dict[str, float]:
    """Accept legacy model keys and expose user-facing category names."""
    merged = dict(category_scores)
    if "whitespace_quality" in merged and "space_utilization" not in merged:
        merged["space_utilization"] = merged["whitespace_quality"]
    defaults = _default_category_scores(visual_score)
    return {
        key: round(float(merged.get(key, defaults[key])), 1)
        for key in defaults
    }


def compute_visual_score_result(
    review: QualitativeSlideReview,
    *,
    visual_score: float | None = None,
    category_scores: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Build visual scoring payload from a qualitative slide review.

    Uses model-supplied scores when present; otherwise derives from issues.
    """
    score = visual_score if visual_score is not None else _score_from_issues(review)
    cats = _normalize_category_scores(
        category_scores or {},
        score,
    )

    has_fail_issues = any(
        issue.category != QualitativeCategory.NO_ISSUE
        and issue.severity in ("high", "medium")
        for issue in review.issues
    )
    passed = score >= VISUAL_PASS_THRESHOLD and not has_fail_issues

    return {
        "visual_score": score,
        "visual_pass": passed,
        "category_scores": cats,
        "overall_quality": review.overall_quality,
        "status": review.status.value,
    }


def compute_deck_visual_score(
    slide_results: list[dict[str, Any]],
) -> float | None:
    scores = [
        float(s["visual_score"])
        for s in slide_results
        if s.get("visual_score") is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def combine_hybrid_score(
    deterministic_score: float | None,
    visual_score: float | None,
    *,
    deterministic_weight: float = 0.70,
    visual_weight: float = 0.30,
) -> float | None:
    """Weighted final score when both layers ran."""
    if deterministic_score is None and visual_score is None:
        return None
    if deterministic_score is None:
        return visual_score
    if visual_score is None:
        return deterministic_score
    total_w = deterministic_weight + visual_weight
    if total_w <= 0:
        return deterministic_score
    det_w = deterministic_weight / total_w
    vis_w = visual_weight / total_w
    return round(deterministic_score * det_w + visual_score * vis_w, 1)
