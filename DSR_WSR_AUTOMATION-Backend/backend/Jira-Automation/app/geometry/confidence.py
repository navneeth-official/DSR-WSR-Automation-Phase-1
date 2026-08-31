"""Confidence gating for qualitative vision findings."""

from __future__ import annotations

from dataclasses import dataclass

from app.geometry.metrics import category_supported_by_metrics
from app.geometry.planner import QUALITATIVE_TO_RULES
from app.geometry.types import SlideGeometryReport

HIGH_CONFIDENCE = 0.90
MEDIUM_CONFIDENCE = 0.60


@dataclass(frozen=True)
class GatedQualitativeIssue:
    category: str
    severity: str
    confidence: float
    description: str
    allow_correction: bool
    gate_reason: str


def gate_qualitative_issue(
    issue: dict,
    slide: SlideGeometryReport,
) -> GatedQualitativeIssue:
    """
    Apply confidence gating policy.

    >= 0.90: allow geometry correction (even if only qualitative).
    0.60–0.90: allow only if geometry detects compatible violation.
    < 0.60: log only, no automatic correction.
    """
    category = str(issue.get("category") or "no_issue")
    confidence = float(issue.get("confidence") or 0.0)
    severity = str(issue.get("severity") or "low")
    description = str(issue.get("description") or "")

    if category == "no_issue":
        return GatedQualitativeIssue(
            category=category,
            severity=severity,
            confidence=confidence,
            description=description,
            allow_correction=False,
            gate_reason="no_issue",
        )

    if category == "clipped_text":
        return GatedQualitativeIssue(
            category=category,
            severity=severity,
            confidence=confidence,
            description=description,
            allow_correction=False,
            gate_reason="clipped_text requires visual confirmation; geometry cannot measure glyphs",
        )

    if confidence >= HIGH_CONFIDENCE:
        return GatedQualitativeIssue(
            category=category,
            severity=severity,
            confidence=confidence,
            description=description,
            allow_correction=True,
            gate_reason="high_confidence",
        )

    if confidence >= MEDIUM_CONFIDENCE:
        if qualitative_compatible_with_geometry(category, slide):
            return GatedQualitativeIssue(
                category=category,
                severity=severity,
                confidence=confidence,
                description=description,
                allow_correction=True,
                gate_reason="medium_confidence_with_geometry_confirmation",
            )
        return GatedQualitativeIssue(
            category=category,
            severity=severity,
            confidence=confidence,
            description=description,
            allow_correction=False,
            gate_reason="medium_confidence_without_geometry_confirmation",
        )

    return GatedQualitativeIssue(
        category=category,
        severity=severity,
        confidence=confidence,
        description=description,
        allow_correction=False,
        gate_reason="low_confidence_logged_only",
    )


def qualitative_compatible_with_geometry(
    category: str, slide: SlideGeometryReport
) -> bool:
    """True when geometry rules or derived metrics support the qualitative category."""
    expected = QUALITATIVE_TO_RULES.get(category, ())
    if expected:
        rule_ids = {v.rule_id for v in slide.violations}
        if rule_ids & set(expected):
            return True
    return category_supported_by_metrics(category, slide.metrics)


def categories_for_correction(gated: list[GatedQualitativeIssue]) -> tuple[str, ...]:
    return tuple(
        g.category
        for g in gated
        if g.allow_correction and g.category != "no_issue"
    )


def requires_manual_review(
    gated: list[GatedQualitativeIssue],
    slide: SlideGeometryReport,
    *,
    correction_applied: bool,
) -> tuple[bool, list[str]]:
    """
    Mark manual review when qualitative issue persists but geometry cannot fix.
    """
    reasons: list[str] = []
    for g in gated:
        if g.category == "no_issue":
            continue
        if g.gate_reason == "low_confidence_logged_only":
            reasons.append(f"[logged] {g.category}: {g.description}")
            continue
        if not g.allow_correction:
            reasons.append(f"{g.category} (confidence {g.confidence:.2f}): {g.description}")
        elif not correction_applied and not slide.has_violations:
            if not category_supported_by_metrics(g.category, slide.metrics):
                reasons.append(
                    f"{g.category}: {g.description} — no deterministic geometry strategy"
                )
    return bool(reasons), reasons
