"""Filter qualitative vision findings — geometry is deterministic, not vision."""

from __future__ import annotations

import re
from typing import Any

from app.constants.vision_qualitative_reviewer_prompt import (
    LEGACY_GEOMETRY_CATEGORIES,
    VISUAL_SCORE_PASS_THRESHOLD,
)

_GEOMETRY_MEASUREMENT_PATTERNS = re.compile(
    r"\b\d+(\.\d+)?\s*(in|inch|inches|px|pixels|pt|points|emu)\b|"
    r"\boverlap(s|ping)?\b|\bclip(ped|ping)?\b|\bfooter\s+(zone|violation)\b|"
    r"\btext_ka_clearance\b|\bhl_ka_gap\b|\bhl_waste_below_text\b",
    re.I,
)

# Vision model must never fail a slide solely because KA is empty (manual entry).
_EMPTY_KA_DESCRIPTION_PATTERNS = re.compile(
    r"("
    r"key\s+activit(?:y|ies).{0,140}?(?:empty|blank|no\s+content|entirely\s+empty|"
    r"lacks?\s+content|no\s+items?|unused|not\s+filled|without\s+content|unfilled)|"
    r"(?:empty|blank|entirely\s+empty).{0,80}?key\s+activit(?:y|ies)|"
    r"ka\s+(?:tab|section|table|box).{0,60}?(?:empty|blank|no\s+content|unused)|"
    r"(?:large|excessive|unused).{0,80}?(?:whitespace|white\s+space).{0,80}?"
    r"(?:below|under|in|inside).{0,40}?key\s+activit|"
    r"slide\s+(?:feels?|looks?|appears?)\s+incomplete.{0,80}?"
    r"(?:key\s+activit|ka\s+(?:tab|section))|"
    r"lack\s+of\s+content\s+in\s+the\s+key\s+activit|"
    r"off[\s-]?template.{0,80}?(?:empty|lack).{0,40}?key\s+activit|"
    r"poor_visual_balance.{0,100}?key\s+activit.{0,80}?"
    r"(?:empty|completely\s+empty|entirely\s+empty)|"
    r"weak_hierarchy.{0,100}?empty\s+key\s+activit|"
    r"dense(?:ly)?\s+packed.{0,80}?key\s+activit.{0,60}?empty|"
    r"key\s+activit.{0,60}?(?:empty|completely\s+empty).{0,80}?lopsided|"
    r"disproportionately\s+empty.{0,80}?(?:below|under).{0,40}?key\s+activit|"
    r"only\s+(?:the\s+)?key\s+activit.{0,60}?(?:empty|blank)|"
    r"ka[\s-]?only[\s-]?contd.{0,80}?(?:unfinished|incomplete|off[\s-]?template)"
    r")",
    re.I | re.DOTALL,
)

_HL_LAYOUT_DESCRIPTION_PATTERNS = re.compile(
    r"("
    r"highlights?.{0,100}?(?:oversized|stretched|too\s+large|too\s+tall|"
    r"disproportionat|sparse|under[\s-]?utiliz|wasteful|empty\s+below|"
    r"inside\s+the\s+hl|inside\s+the\s+gray|gray\s+box)|"
    r"\bhl\s+(?:tab|box|gray|area).{0,80}?(?:oversized|stretched|too\s+large|sparse)|"
    r"premature.{0,40}?(?:contd|continuation)|"
    r"(?:contd|continuation).{0,60}?premature|"
    r"hl_oversized_for_content|"
    r"premature_hl_continuation|"
    r"content.{0,60}?(?:could|should).{0,40}?fit\s+on\s+(?:the\s+)?main|"
    r"main\s+slide.{0,60}?(?:under[\s-]?utiliz|room\s+for\s+more)"
    r")",
    re.I | re.DOTALL,
)

_EMPTY_KA_CATEGORIES = frozenset({
    "excessive_whitespace",
    "poor_visual_balance",
    "weak_hierarchy",
    "off_template",
})

_HL_FOCUS_CATEGORIES = frozenset({
    "hl_oversized_for_content",
    "premature_hl_continuation",
    "cramped_layout",
})

_EMPTY_KA_SUPPRESS_REASON = "suppressed: empty Key Activities is expected (manual entry)"
_PREMATURE_CONTD_FULL_MAIN_REASON = (
    "suppressed: main slide HL is at capacity (effective utilization ≥ 100%)"
)
_BENIGN_SUPPRESS_REASONS = frozenset({
    _EMPTY_KA_SUPPRESS_REASON,
    _PREMATURE_CONTD_FULL_MAIN_REASON,
})

# Deterministic HL container rules — layout layer owns the user-facing message.
HL_CONTAINER_LAYOUT_RULES = frozenset({"CONT-HL-01", "CONT-SPARSE-01", "HL-SIZE-01"})
LAYOUT_OWNED_VISION_CATEGORIES = frozenset({
    "hl_oversized_for_content",
})
_LAYOUT_OWNED_SUPPRESS_REASON = (
    "suppressed: layout-owned HL container finding (deterministic rule)"
)


def _main_hl_at_capacity_from_ctx(slide_ctx: dict[str, Any]) -> bool:
    cross = slide_ctx.get("cross_slide_hl") or {}
    if cross.get("main_hl_at_capacity"):
        return True
    util = cross.get("main_hl_effective_utilization")
    if util is not None and float(util) >= 1.0:
        return True
    metrics = slide_ctx.get("layout_metrics") or {}
    util = metrics.get("highlights_effective_utilization_ratio")
    return util is not None and float(util) >= 1.0


def _is_premature_contd_on_full_main_issue(
    issue: dict[str, Any],
    slide_ctx: dict[str, Any],
) -> bool:
    if str(issue.get("category") or "") != "premature_hl_continuation":
        return False
    return _main_hl_at_capacity_from_ctx(slide_ctx)


def _deterministic_violations_from_ctx(slide_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    deterministic = slide_ctx.get("deterministic_violations") or []
    if not deterministic:
        layout_metrics = slide_ctx.get("layout_metrics") or {}
        deterministic = layout_metrics.get("deterministic_violations") or []
    return list(deterministic)


def layout_owns_hl_container_finding(
    deterministic_violations: list[dict[str, Any]],
) -> bool:
    """True when measurable layout rules already cover HL container sizing."""
    rules = {str(v.get("rule_id") or "") for v in deterministic_violations}
    return bool(rules & HL_CONTAINER_LAYOUT_RULES)


def _is_layout_owned_vision_duplicate(
    issue: dict[str, Any],
    deterministic_violations: list[dict[str, Any]],
) -> bool:
    if not layout_owns_hl_container_finding(deterministic_violations):
        return False
    category = str(issue.get("category") or "")
    if category in LAYOUT_OWNED_VISION_CATEGORIES:
        return True
    if category == "excessive_whitespace":
        description = str(issue.get("description") or "")
        return _describes_hl_layout_issue(description, category)
    return False


def _is_legacy_geometry_issue(issue: dict[str, Any]) -> bool:
    category = str(issue.get("category") or "")
    return category in LEGACY_GEOMETRY_CATEGORIES


def _empty_ka_expected(slide_ctx: dict[str, Any]) -> bool:
    policy = slide_ctx.get("review_policy") or {}
    if policy.get("empty_key_activities_is_valid"):
        return True
    layout_type = str(slide_ctx.get("layout_type") or "")
    if layout_type == "ka_only_contd":
        return True
    metrics = slide_ctx.get("layout_metrics") or {}
    ka_count = metrics.get("key_activities_item_count")
    if slide_ctx.get("has_key_activities_section") and (ka_count is None or ka_count == 0):
        return True
    return False


def _describes_empty_ka_issue(description: str) -> bool:
    return bool(_EMPTY_KA_DESCRIPTION_PATTERNS.search(description))


def _describes_hl_layout_issue(description: str, category: str) -> bool:
    if category in _HL_FOCUS_CATEGORIES:
        return True
    return bool(_HL_LAYOUT_DESCRIPTION_PATTERNS.search(description))


def _is_empty_ka_whitespace_issue(
    issue: dict[str, Any],
    slide_ctx: dict[str, Any],
) -> bool:
    """True when the finding is only about empty KA / whitespace below KA."""
    if not _empty_ka_expected(slide_ctx):
        return False

    category = str(issue.get("category") or "")
    description = str(issue.get("description") or "")

    if category in _HL_FOCUS_CATEGORIES:
        return False

    if _describes_hl_layout_issue(description, category):
        return False

    if category in _EMPTY_KA_CATEGORIES and _describes_empty_ka_issue(description):
        return True

    if category == "excessive_whitespace" and _describes_empty_ka_issue(description):
        return True

    if layout_type := str(slide_ctx.get("layout_type") or ""):
        if layout_type == "ka_only_contd" and category in _EMPTY_KA_CATEGORIES:
            return True

    return _describes_empty_ka_issue(description)


def should_suppress_vision_issue(
    issue: dict[str, Any],
    slide_ctx: dict[str, Any],
    **_: Any,
) -> tuple[bool, str]:
    """
    Suppress vision issues that belong to deterministic geometry validation,
    or that incorrectly penalize empty Key Activities (manual-entry placeholder).
    """
    if _is_legacy_geometry_issue(issue):
        return True, "suppressed: geometry category handled by deterministic evaluator"

    description = str(issue.get("description") or "")
    if _GEOMETRY_MEASUREMENT_PATTERNS.search(description):
        return True, "suppressed: issue contains geometry measurements"

    if _is_empty_ka_whitespace_issue(issue, slide_ctx):
        return True, _EMPTY_KA_SUPPRESS_REASON

    if _is_premature_contd_on_full_main_issue(issue, slide_ctx):
        return True, _PREMATURE_CONTD_FULL_MAIN_REASON

    deterministic = _deterministic_violations_from_ctx(slide_ctx)
    if _is_layout_owned_vision_duplicate(issue, deterministic):
        return True, _LAYOUT_OWNED_SUPPRESS_REASON

    det_rules = {str(v.get("rule_id")) for v in deterministic}
    if det_rules and any(
        rule.lower() in description.lower() for rule in det_rules if rule
    ):
        return True, "suppressed: duplicates deterministic violation"

    return False, ""


def filter_vision_issues(
    issues: list[dict[str, Any]],
    slide_ctx: dict[str, Any],
    **kwargs: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (kept_issues, suppressed_issues with reasons)."""
    kept: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for issue in issues:
        suppress, reason = should_suppress_vision_issue(
            issue, slide_ctx, **kwargs
        )
        if suppress:
            suppressed.append({**issue, "suppressed_reason": reason})
        else:
            kept.append(issue)
    return kept, suppressed


_NON_FAILING_VISION_CATEGORIES = frozenset({
    "premature_hl_continuation",
    "no_issue",
})


def vision_issues_fail(issues: list[dict[str, Any]]) -> bool:
    """True when kept subjective issues include medium/high severity findings."""
    return any(
        issue.get("category") not in _NON_FAILING_VISION_CATEGORIES
        and issue.get("severity") in ("high", "medium")
        for issue in issues
    )


def resolve_visual_pass_after_gating(
    *,
    visual_score: float | None,
    kept_issues: list[dict[str, Any]],
    suppressed_issues: list[dict[str, Any]],
    slide_ctx: dict[str, Any],
) -> tuple[bool, float]:
    """
    Final visual pass/score after issue gating.

    When all findings were empty-KA false positives, restore a passing score so
    benign placeholder layouts are not failed.
    """
    score = float(visual_score if visual_score is not None else 0.0)
    has_kept_failures = vision_issues_fail(kept_issues)

    if (
        not has_kept_failures
        and suppressed_issues
        and all(
            s.get("suppressed_reason") in _BENIGN_SUPPRESS_REASONS
            for s in suppressed_issues
        )
    ):
        if score < VISUAL_SCORE_PASS_THRESHOLD:
            score = 88.0
        return True, round(score, 1)

    passed = score >= VISUAL_SCORE_PASS_THRESHOLD and not has_kept_failures
    return passed, round(score, 1)


def supplement_geometry_vision_issues(
    slide_ctx: dict[str, Any],
    *,
    service_chain: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Deprecated — geometry violations are surfaced only by deterministic evaluation.

    Kept for backward compatibility; always returns an empty list.
    """
    _ = slide_ctx, service_chain
    return []


def build_service_chain_by_slide(
    chains: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Map slide index → service chain for cross-slide context."""
    by_slide: dict[int, dict[str, Any]] = {}
    for chain in chains:
        main_idx = chain.get("main_slide_index")
        if main_idx is not None:
            by_slide[int(main_idx)] = chain
        for idx in chain.get("contd_hl_slide_indices") or []:
            by_slide[int(idx)] = chain
        ka_idx = chain.get("ka_only_contd_slide_index")
        if ka_idx is not None:
            by_slide[int(ka_idx)] = chain
    return by_slide
