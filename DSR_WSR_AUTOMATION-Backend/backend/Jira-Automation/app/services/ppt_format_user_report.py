"""User-facing evaluation report — business-readable output without internal metrics."""

from __future__ import annotations

import re
from typing import Any, Literal

from app.services.ppt_format_report import DeckFormatReport, SlideFormatResult
from app.services.template_calibration import TemplateLayoutThresholds, load_thresholds
from app.vision.issue_gating import (
    LAYOUT_OWNED_VISION_CATEGORIES,
    layout_owns_hl_container_finding,
)

Rating = Literal["Excellent", "Good", "Needs Improvement"]
CategoryStatus = Literal["pass", "needs_improvement", "fail"]

_MEASUREMENT_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s*(in|inch|inches|px|pixels|pt|points|emu|%)\b|"
    r"\blimit\s+\d|effective utilization|hl_waste|utilization ratio|"
    r"\(limit\s+[^)]+\)",
    re.I,
)

_USER_VISUAL_MESSAGES: dict[str, str] = {
    "hl_oversized_for_content": (
        "Highlights container contains excessive unused space. "
        "Shrink the Highlights table to fit the content."
    ),
    "poor_visual_balance": "The Highlights area looks unbalanced on the slide.",
    "excessive_whitespace": "There is excessive empty space inside the Highlights area.",
    "cramped_layout": "The slide layout feels overcrowded.",
    "weak_hierarchy": "Text hierarchy is hard to scan quickly.",
    "off_template": "Formatting diverges from the G10X WSR template.",
}

# --- Deterministic rule_id → user-facing objective category ---
_OBJECTIVE_TYPOGRAPHY = frozenset({
    "HL-HDR-01", "HL-HDR-02", "HL-HDR-03",
    "HL-P-01", "HL-P-02", "HL-P-03", "HL-P-04", "HL-P-05", "HL-P-06",
    "HL-SPC-01", "HL-SPC-02", "HL-SPC-03", "HL-SPC-04",
    "KA-01", "KA-02", "KA-03", "KA-04",
})
_OBJECTIVE_ALIGNMENT = frozenset({"KA-PLC-02", "KA-PLC-03"})
_OBJECTIVE_OVERFLOW = frozenset({"KA-OVERLAP-01", "HL-OVERFLOW-01"})
_OBJECTIVE_FOOTER = frozenset({"GEO-02", "GEO-01", "GEO-03"})
_OBJECTIVE_TEMPLATE = frozenset({"TITLE-01", "TITLE-02", "TITLE-03"})
_OBJECTIVE_CONTAINER = frozenset({"KA-PLC-04"})

# Measured layout rules → layout evaluation (not objective failures in user view)
_LAYOUT_CONTAINER_FIT = frozenset({"CONT-HL-01", "CONT-SPARSE-01", "HL-SIZE-01", "KA-SIZE-01"})
_LAYOUT_SECTION_GAP = frozenset({"KA-PLC-02"})

# Vision categories
_VISUAL_TEMPLATE = frozenset({"off_template", "weak_hierarchy"})
_VISUAL_BALANCE = frozenset({
    "poor_visual_balance", "cramped_layout", "hl_oversized_for_content",
})
_VISUAL_SPACE = frozenset({"excessive_whitespace"})
_SUGGESTION_ONLY_VISION = frozenset({"premature_hl_continuation"})

_USER_VISUAL_CATEGORIES = (
    "template_consistency",
    "typography",
    "alignment",
    "visual_balance",
    "readability",
    "space_utilization",
    "presentation_quality",
)

_CATEGORY_LABELS = {
    "template_consistency": "Template Consistency",
    "typography": "Typography",
    "alignment": "Alignment",
    "overflow_and_clipping": "Overflow & Clipping",
    "container_boundaries": "Container Boundaries",
    "footer_safety": "Footer Safety",
    "template_compliance": "Template Compliance",
    "container_fit": "Container Fit",
    "space_utilization": "Space Utilization",
    "section_separation": "Section Separation",
    "visual_balance": "Visual Balance",
    "readability": "Readability",
    "presentation_quality": "Presentation Quality",
}


def _status_from_violations(violations: list[dict[str, Any]]) -> CategoryStatus:
    if not violations:
        return "pass"
    if any(v.get("severity") == "critical" for v in violations):
        return "fail"
    return "needs_improvement"


def _sanitize_user_message(text: str) -> str:
    """Remove internal measurements and jargon from user-visible strings."""
    cleaned = _MEASUREMENT_PATTERN.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;—")
    return cleaned or text


def _user_message_for_visual_issue(issue: dict[str, Any]) -> str:
    category = str(issue.get("category") or "")
    if category in _USER_VISUAL_MESSAGES:
        return _USER_VISUAL_MESSAGES[category]
    description = str(issue.get("description") or "")
    if description:
        sanitized = _sanitize_user_message(description)
        if sanitized and not _MEASUREMENT_PATTERN.search(sanitized):
            return sanitized
    return "Visual quality could be improved in this area."


def _user_messages_from_violations(violations: list[dict[str, Any]]) -> list[str]:
    return [
        _sanitize_user_message(str(v.get("message") or v.get("rule_id") or "Issue detected"))
        for v in violations
    ]


def _section_separation_rating(
    gap_in: float | None,
    *,
    thresholds: TemplateLayoutThresholds,
) -> Rating:
    if gap_in is None:
        return "Good"
    target = thresholds.hl_ka_border_gap_target_in
    max_gap = thresholds.hl_ka_border_gap_max_in
    if gap_in <= target + 0.02:
        return "Excellent"
    if gap_in <= max_gap:
        return "Good"
    return "Needs Improvement"


def _container_fit_messages(
    slide: dict[str, Any],
    layout_violations: list[dict[str, Any]],
) -> tuple[CategoryStatus, list[str]]:
    if layout_violations:
        messages: list[str] = []
        for v in layout_violations:
            rid = v.get("rule_id", "")
            if rid == "CONT-HL-01":
                messages.append(
                    "Highlights container on this continuation slide contains "
                    "excessive unused space. Consider shrinking the Highlights table "
                    "to fit the overflow content."
                )
            elif rid in ("HL-SIZE-01", "CONT-SPARSE-01"):
                messages.append(
                    "Highlights container contains excessive unused space."
                )
            elif rid == "KA-SIZE-01":
                messages.append(
                    "Key Activities container contains excessive unused space."
                )
            else:
                messages.append(str(v.get("message") or "Container sizing needs adjustment."))
        return _status_from_violations(layout_violations), messages

    hl = slide.get("highlights") or {}
    ka = slide.get("key_activities")
    messages_ok: list[str] = []
    if hl:
        messages_ok.append("Highlights container is appropriately sized.")
    if ka is not None:
        messages_ok.append("Key Activities container is appropriately sized.")
    if not messages_ok:
        return "pass", ["Layout containers are appropriately sized."]
    return "pass", messages_ok


def _space_utilization_messages(
    slide: dict[str, Any],
    layout_violations: list[dict[str, Any]],
    visual_issues: list[dict[str, Any]],
    *,
    layout_owns_hl_container: bool = False,
) -> tuple[CategoryStatus, list[str]]:
    if layout_owns_hl_container:
        unrelated_visual = [
            i for i in visual_issues
            if i.get("category") in _VISUAL_SPACE
            and i.get("category") not in LAYOUT_OWNED_VISION_CATEGORIES
        ]
        if unrelated_visual:
            msgs = [_user_message_for_visual_issue(i) for i in unrelated_visual]
            return "needs_improvement", msgs
        return "pass", ["Slide space is balanced."]

    space_visual = [
        i for i in visual_issues
        if i.get("category") in _VISUAL_SPACE | {"hl_oversized_for_content"}
    ]
    if layout_violations or space_visual:
        msgs: list[str] = []
        if layout_violations:
            msgs.append(
                "Slide space is not used efficiently — large empty regions "
                "inside content containers."
            )
        for issue in space_visual:
            msg = _user_message_for_visual_issue(issue)
            if msg not in msgs:
                msgs.append(msg)
        return "needs_improvement", msgs or ["Space utilization needs improvement."]

    hl = slide.get("highlights") or {}
    util = hl.get("effective_utilization_ratio", hl.get("utilization_ratio"))
    if util is not None and float(util) >= 0.85:
        return "pass", ["Slide space is used efficiently."]
    if slide.get("is_contd"):
        return "pass", ["Continuation slide uses space appropriately for overflow content."]
    return "pass", ["Slide space is balanced."]


def _split_violations(violations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "typography": [],
        "alignment": [],
        "overflow_and_clipping": [],
        "container_boundaries": [],
        "footer_safety": [],
        "template_compliance": [],
        "container_fit": [],
        "section_separation": [],
    }
    for v in violations:
        rid = str(v.get("rule_id") or "")
        if rid in _OBJECTIVE_TYPOGRAPHY:
            buckets["typography"].append(v)
        elif rid in _OBJECTIVE_ALIGNMENT:
            buckets["alignment"].append(v)
        elif rid in _OBJECTIVE_OVERFLOW:
            buckets["overflow_and_clipping"].append(v)
        elif rid in _OBJECTIVE_FOOTER:
            buckets["footer_safety"].append(v)
        elif rid in _OBJECTIVE_TEMPLATE:
            buckets["template_compliance"].append(v)
        elif rid in _OBJECTIVE_CONTAINER:
            buckets["container_boundaries"].append(v)
        elif rid in _LAYOUT_CONTAINER_FIT:
            buckets["container_fit"].append(v)
        elif rid in _LAYOUT_SECTION_GAP:
            buckets["section_separation"].append(v)
        else:
            buckets["container_boundaries"].append(v)
    return buckets


def _visual_category_entry(
    key: str,
    score: float | None,
    issues: list[dict[str, Any]],
    *,
    default_pass_msg: str,
    suppress_score_fallback: bool = False,
) -> dict[str, Any]:
    status: CategoryStatus = "pass"
    messages: list[str] = []
    if issues:
        status = "needs_improvement"
        messages = [_user_message_for_visual_issue(i) for i in issues]
    elif score is not None and score < 70 and not suppress_score_fallback:
        status = "needs_improvement"
        messages = [f"{_CATEGORY_LABELS.get(key, key)} could be improved."]
    else:
        messages = [default_pass_msg]
    entry: dict[str, Any] = {"status": status, "messages": messages}
    if score is not None:
        entry["score"] = round(float(score), 1)
    return entry


def _map_visual_scores(category_scores: dict[str, float]) -> dict[str, float]:
    """Map model category keys to user-facing visual keys."""
    mapped = dict(category_scores)
    if "whitespace_quality" in mapped and "space_utilization" not in mapped:
        mapped["space_utilization"] = mapped["whitespace_quality"]
    if "presentation_quality" in mapped and "template_consistency" not in mapped:
        mapped["template_consistency"] = mapped["presentation_quality"]
    return mapped


def build_slide_user_evaluation(
    slide_result: SlideFormatResult,
    slide_data: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds | None = None,
) -> dict[str, Any]:
    """Transform one slide's internal results into a user-facing evaluation."""
    thresholds = thresholds or load_thresholds()
    buckets = _split_violations(slide_result.violations)
    layout_owns_hl_container = layout_owns_hl_container_finding(buckets["container_fit"])

    visual_issues = [
        i for i in slide_result.visual_issues
        if i.get("category") not in _SUGGESTION_ONLY_VISION
        and not (
            layout_owns_hl_container
            and i.get("category") in LAYOUT_OWNED_VISION_CATEGORIES
        )
    ]
    suggestions = list(slide_result.suggestions)

    vis_scores = _map_visual_scores(slide_result.category_scores)
    gap = slide_data.get("hl_ka_gap_in")
    sep_rating = _section_separation_rating(
        float(gap) if gap is not None else None,
        thresholds=thresholds,
    )

    container_status, container_msgs = _container_fit_messages(
        slide_data, buckets["container_fit"]
    )
    space_status, space_msgs = _space_utilization_messages(
        slide_data,
        buckets["container_fit"],
        visual_issues,
        layout_owns_hl_container=layout_owns_hl_container,
    )

    objective_categories = {
        "typography": {
            "status": _status_from_violations(buckets["typography"]),
            "messages": _user_messages_from_violations(buckets["typography"])
            or ["Typography matches the G10X template."],
        },
        "alignment": {
            "status": _status_from_violations(buckets["alignment"] + buckets["section_separation"]),
            "messages": _user_messages_from_violations(buckets["alignment"])
            or ["Text boxes and tables are aligned consistently."],
        },
        "overflow_and_clipping": {
            "status": _status_from_violations(buckets["overflow_and_clipping"]),
            "messages": _user_messages_from_violations(buckets["overflow_and_clipping"])
            or ["No text clipping or overlap detected."],
        },
        "container_boundaries": {
            "status": _status_from_violations(buckets["container_boundaries"]),
            "messages": _user_messages_from_violations(buckets["container_boundaries"])
            or ["Content stays within container boundaries."],
        },
        "footer_safety": {
            "status": _status_from_violations(buckets["footer_safety"]),
            "messages": _user_messages_from_violations(buckets["footer_safety"])
            or ["Content does not intrude into the footer area."],
        },
        "template_compliance": {
            "status": _status_from_violations(buckets["template_compliance"]),
            "messages": _user_messages_from_violations(buckets["template_compliance"])
            or ["Slide follows G10X WSR template conventions."],
        },
    }

    layout_categories = {
        "container_fit": {"status": container_status, "messages": container_msgs},
        "space_utilization": {"status": space_status, "messages": space_msgs},
        "section_separation": {
            "rating": sep_rating,
            "messages": _user_messages_from_violations(buckets["section_separation"])
            or [f"Spacing between sections is {sep_rating.lower()}."],
        },
    }

    template_issues = [
        i for i in visual_issues if i.get("category") in _VISUAL_TEMPLATE
    ]
    balance_issues = [
        i for i in visual_issues
        if i.get("category") in _VISUAL_BALANCE
        and not (
            layout_owns_hl_container
            and i.get("category") in LAYOUT_OWNED_VISION_CATEGORIES
        )
    ]
    readability_issues = [
        i for i in visual_issues if i.get("category") == "weak_hierarchy"
    ]

    visual_categories = {
        "template_consistency": _visual_category_entry(
            "template_consistency",
            vis_scores.get("template_consistency"),
            template_issues,
            default_pass_msg="Formatting is consistent with the G10X WSR template.",
        ),
        "visual_balance": _visual_category_entry(
            "visual_balance",
            vis_scores.get("visual_balance"),
            balance_issues,
            default_pass_msg="The slide feels visually balanced.",
            suppress_score_fallback=layout_owns_hl_container,
        ),
        "readability": _visual_category_entry(
            "readability",
            vis_scores.get("readability"),
            readability_issues,
            default_pass_msg="Text is easy to read with clear hierarchy.",
        ),
        "space_utilization": _visual_category_entry(
            "space_utilization",
            vis_scores.get("space_utilization"),
            [i for i in visual_issues if i.get("category") in _VISUAL_SPACE],
            default_pass_msg="Slide space is used efficiently.",
            suppress_score_fallback=layout_owns_hl_container,
        ),
        "presentation_quality": _visual_category_entry(
            "presentation_quality",
            vis_scores.get("presentation_quality"),
            [],
            default_pass_msg="Slide looks professional and client-ready.",
        ),
    }

    objective_pass = all(
        c["status"] == "pass" for c in objective_categories.values()
    )
    layout_pass = (
        container_status == "pass"
        and space_status == "pass"
        and sep_rating != "Needs Improvement"
    )

    return {
        "slide_index": slide_result.slide_index,
        "title": slide_result.title,
        "pass": slide_result.passed,
        "scores": {
            "overall": slide_result.final_score,
            "objective": slide_result.deterministic_score,
            "visual": slide_result.visual_score,
        },
        "evaluation": {
            "objective": {
                "pass": objective_pass,
                "categories": objective_categories,
            },
            "layout": {
                "pass": layout_pass,
                "categories": layout_categories,
            },
            "visual": {
                "pass": slide_result.visual_pass,
                "categories": visual_categories,
            },
        },
        "suggestions": suggestions,
    }


def _slide_has_visual_review(slide: SlideFormatResult) -> bool:
    return (
        slide.visual_score is not None
        or slide.visual_pass is not None
        or bool(slide.visual_issues)
        or bool(slide.strengths)
        or bool(slide.category_scores)
    )


def build_ai_visual_evaluation_report(report: DeckFormatReport) -> dict[str, Any]:
    """Structured visual AI review results (per-slide scores, issues, strengths)."""
    visual_slides = [s for s in report.slides if _slide_has_visual_review(s)]
    n_pass = sum(1 for s in visual_slides if s.visual_pass is True)
    n_fail = sum(1 for s in visual_slides if s.visual_pass is False)

    return {
        "source_file": report.source_file,
        "vision_model": report.vision_model or "unknown",
        "deck_visual_pass": n_fail == 0 if visual_slides else None,
        "summary": {
            "slides_reviewed": len(visual_slides),
            "slides_pass": n_pass,
            "slides_fail": n_fail,
            "deck_visual_score": report.visual_score,
        },
        "slides": [
            {
                "slide_index": slide.slide_index,
                "title": slide.title,
                "visual_pass": slide.visual_pass,
                "visual_score": slide.visual_score,
                "category_scores": dict(slide.category_scores),
                "issues": list(slide.visual_issues),
                "strengths": list(slide.strengths),
                "suggestions": list(slide.suggestions),
            }
            for slide in visual_slides
        ],
    }


def format_ai_visual_evaluation_text(ai_report: dict[str, Any]) -> str:
    """Human-readable visual AI review report."""
    summary = ai_report.get("summary") or {}
    lines = [
        f"Visual AI Review ({ai_report.get('vision_model', 'unknown')})",
        f"Deck: {ai_report.get('source_file', '')}",
    ]
    if summary.get("deck_visual_score") is not None:
        lines.append(f"Deck visual score: {summary['deck_visual_score']}/100")
    if summary.get("slides_reviewed"):
        lines.append(
            f"Slides: {summary.get('slides_pass', 0)}/{summary['slides_reviewed']} pass"
        )
    lines.append("")
    lines.append("Per slide:")
    for slide in ai_report.get("slides", []):
        status = "PASS" if slide.get("visual_pass") else "FAIL"
        score = slide.get("visual_score")
        score_s = f"  score {score}" if score is not None else ""
        lines.append(
            f"  Slide {slide['slide_index']:2d}  {status}{score_s}  "
            f"{slide.get('title', '')[:55]}"
        )
        categories = slide.get("category_scores") or {}
        if categories:
            parts = [f"{k}={v}" for k, v in sorted(categories.items())]
            lines.append(f"    Scores: {', '.join(parts)}")
        for issue in slide.get("issues", [])[:3]:
            cat = issue.get("category", "?")
            desc = str(issue.get("description") or "")[:90]
            lines.append(f"    Issue [{cat}]: {desc}")
        for strength in slide.get("strengths", [])[:2]:
            lines.append(f"    Strength: {str(strength)[:90]}")
        for sug in slide.get("suggestions", [])[:1]:
            lines.append(f"    Suggestion: {sug.get('message', '')[:90]}")
    lines.append("")
    deck_pass = ai_report.get("deck_visual_pass")
    if deck_pass is not None:
        lines.append(f"Overall visual: {'PASS' if deck_pass else 'FAIL'}")
    return "\n".join(lines)


def build_user_evaluation_report(
    report: DeckFormatReport,
    deck_data: dict[str, Any],
) -> dict[str, Any]:
    """Build the business-user evaluation document."""
    slides_by_index = {
        int(s["slide_index"]): s for s in deck_data.get("slides", [])
    }
    user_slides = [
        build_slide_user_evaluation(
            slide_result,
            slides_by_index.get(slide_result.slide_index, {}),
        )
        for slide_result in report.slides
    ]

    all_suggestions = [
        s for slide in user_slides for s in slide.get("suggestions", [])
    ]

    return {
        "source_file": report.source_file,
        "mode": report.mode,
        "deck_pass": report.deck_pass,
        "summary": report.summary,
        "scores": {
            "overall": report.final_score,
            "objective": report.deterministic_score,
            "visual": report.visual_score,
        },
        "slides": user_slides,
        "suggestions": all_suggestions,
        "critical_issues": [
            issue for issue in report.critical_issues
            if not any(kw in issue.lower() for kw in ("hl_waste", "utilization", "0."))
        ] or report.critical_issues,
    }


def format_user_evaluation_text(user_report: dict[str, Any]) -> str:
    """Human-readable business report."""
    lines = [
        f"Deck: {user_report.get('source_file', '')}",
        f"Result: {'PASS' if user_report.get('deck_pass') else 'FAIL'}",
    ]
    scores = user_report.get("scores") or {}
    if scores.get("overall") is not None:
        lines.append(f"Overall score: {scores['overall']}/100")
    if user_report.get("summary"):
        lines.append(user_report["summary"])
    lines.append("")
    lines.append("Per slide:")
    for slide in user_report.get("slides", []):
        status = "PASS" if slide.get("pass") else "FAIL"
        lines.append(f"  Slide {slide['slide_index']:2d}  {status}  {slide.get('title', '')[:55]}")
        obj = slide.get("evaluation", {}).get("objective", {})
        lay = slide.get("evaluation", {}).get("layout", {})
        vis = slide.get("evaluation", {}).get("visual", {})
        if obj and not obj.get("pass"):
            lines.append("    Objective: needs attention")
            for cat, data in (obj.get("categories") or {}).items():
                if data.get("status") != "pass":
                    for msg in data.get("messages", [])[:2]:
                        lines.append(f"      - {_CATEGORY_LABELS.get(cat, cat)}: {msg[:80]}")
        if lay and not lay.get("pass"):
            lines.append("    Layout: needs attention")
            for cat, data in (lay.get("categories") or {}).items():
                if data.get("status") == "needs_improvement" or data.get("rating") == "Needs Improvement":
                    for msg in data.get("messages", [])[:2]:
                        lines.append(f"      - {_CATEGORY_LABELS.get(cat, cat)}: {msg[:80]}")
        if vis and vis.get("pass") is False:
            visual_lines: list[str] = []
            for cat, data in (vis.get("categories") or {}).items():
                if data.get("status") != "pass":
                    for msg in data.get("messages", [])[:1]:
                        visual_lines.append(
                            f"      - {_CATEGORY_LABELS.get(cat, cat)}: {msg[:80]}"
                        )
            if visual_lines:
                lines.append("    Visual: needs attention")
                lines.extend(visual_lines)
        for sug in slide.get("suggestions", [])[:2]:
            lines.append(f"    Suggestion: {sug.get('message', '')[:90]}")
    if user_report.get("suggestions"):
        lines.extend(["", "Deck suggestions:"])
        for sug in user_report["suggestions"][:5]:
            lines.append(f"  - Slide {sug.get('slide_index', '?')}: {sug.get('message', '')[:90]}")
    lines.append("")
    lines.append(f"Overall: {'PASS' if user_report.get('deck_pass') else 'FAIL'}")
    return "\n".join(lines)


def format_evaluation_for_terminal(
    report: DeckFormatReport,
    *,
    debug: bool = False,
) -> str:
    """User-facing terminal output by default; pass debug=True for developer view."""
    if debug:
        from app.services.ppt_format_report import format_deck_pass_fail_report

        return format_deck_pass_fail_report(report)

    deck_data = report.deck_data or {"slides": []}
    user_report = build_user_evaluation_report(report, deck_data)
    return format_user_evaluation_text(user_report)
