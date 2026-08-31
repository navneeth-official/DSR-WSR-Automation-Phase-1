"""Deterministic scoring from measurable layout violations (source of truth)."""

from __future__ import annotations

from typing import Any

# Rule IDs that always fail the slide regardless of numeric score.
CRITICAL_AUTO_FAIL_RULES = frozenset({
    "KA-OVERLAP-01",
    "HL-OVERFLOW-01",
    "GEO-02",
    "KA-PLC-04",
    "HL-P-04",
})

SEVERITY_DEDUCTIONS: dict[str, int] = {
    "critical": 50,
    "major": 25,
    "minor": 8,
}

DETERMINISTIC_PASS_THRESHOLD = 70.0


def compute_slide_deterministic_score(
    violations: list[dict[str, Any]],
    *,
    base_score: float = 100.0,
) -> dict[str, Any]:
    """
    Score a slide from deterministic violations only.

    Returns score (0-100), pass flag, and whether a critical auto-fail rule fired.
    """
    score = float(base_score)
    has_critical_violation = False
    has_auto_fail = False

    for violation in violations:
        severity = str(violation.get("severity") or "minor").lower()
        rule_id = str(violation.get("rule_id") or "")
        if severity == "critical":
            has_critical_violation = True
        if rule_id in CRITICAL_AUTO_FAIL_RULES:
            has_auto_fail = True
        score -= float(SEVERITY_DEDUCTIONS.get(severity, 5))

    score = round(max(0.0, min(100.0, score)), 1)
    passed = (
        score >= DETERMINISTIC_PASS_THRESHOLD
        and not has_critical_violation
        and not has_auto_fail
    )
    return {
        "deterministic_score": score,
        "deterministic_pass": passed,
        "has_critical_violation": has_critical_violation,
        "has_auto_fail": has_auto_fail,
    }


def compute_deck_deterministic_score(
    slide_results: list[dict[str, Any]],
) -> float | None:
    """Average deterministic score across slides that have one."""
    scores = [
        float(s["deterministic_score"])
        for s in slide_results
        if s.get("deterministic_score") is not None
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)
