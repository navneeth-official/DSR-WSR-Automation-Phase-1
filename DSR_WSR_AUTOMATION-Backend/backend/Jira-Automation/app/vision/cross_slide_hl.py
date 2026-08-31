"""Cross-slide Highlights continuation checks for visual review."""

from __future__ import annotations

from typing import Any

from app.services.ppt_format_violations import (
    _contd_hl_oversized,
    _hl_room_below_table_to_footer,
)
from app.services.template_calibration import TemplateLayoutThresholds, load_thresholds

# Contd overflow small enough that it likely fit on a main slide that was not full.
_MAX_CONTD_FILLED_FOR_PREMATURE_SIGNAL = 8
_SPARSE_CONTD_UTIL_THRESHOLD = 0.50
_MAIN_NOT_FULL_UTIL_THRESHOLD = 0.95
# At or above 100% effective utilization the main HL column is at capacity — contd is valid.
_MAIN_AT_CAPACITY_UTIL_THRESHOLD = 1.0


def _hl_effective_util(slide: dict[str, Any]) -> float | None:
    hl = slide.get("highlights") or {}
    util = hl.get("effective_utilization_ratio", hl.get("utilization_ratio"))
    return float(util) if util is not None else None


def _contd_hl_slides_with_content(contd_slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for slide in contd_slides:
        hl = slide.get("highlights") or {}
        if hl.get("filled_paragraph_count", 0) > 0:
            out.append(slide)
    return out


def _main_hl_at_capacity(main_util: float | None) -> bool:
    """True when main HL effective utilization is at or above 100% (column full)."""
    return (
        main_util is not None
        and main_util >= _MAIN_AT_CAPACITY_UTIL_THRESHOLD
    )


def detect_premature_hl_continuation(
    main: dict[str, Any],
    contd_hl_slides: list[dict[str, Any]],
    thresholds: TemplateLayoutThresholds,
) -> tuple[bool, str]:
    """
    True when HL (Contd…) exists but the main slide still had capacity for the overflow.

    Uses measured layout only — not slide labels.
    """
    contd_with_hl = _contd_hl_slides_with_content(contd_hl_slides)
    if not contd_with_hl or not main.get("highlights"):
        return False, ""

    main_util = _hl_effective_util(main)
    main_waste = main.get("hl_waste_below_text_in")
    dense_min = thresholds.hl_dense_fill_min_effective_util
    dense_waste_max = thresholds.hl_waste_dense_fill_max_in

    if _main_hl_at_capacity(main_util):
        return False, ""

    if main_util is not None and main_util < dense_min:
        return True, (
            f"Main slide HL effective utilization {main_util:.0%} is below the "
            f"dense-fill band ({dense_min:.0%}) while an HL (Contd…) slide carries "
            f"additional stories."
        )

    if main_waste is not None and main_waste > dense_waste_max:
        return True, (
            f"Main slide has {main_waste} in empty space inside the HL box (above "
            f"the dense-fill band {dense_waste_max} in) while HL overflow was moved "
            f"to a (Contd…) slide."
        )

    for contd in contd_with_hl:
        chl = contd.get("highlights") or {}
        c_util = _hl_effective_util(contd)
        c_filled = int(chl.get("filled_paragraph_count") or 0)
        c_waste = contd.get("hl_waste_below_text_in")
        sparse_contd = (
            c_filled <= _MAX_CONTD_FILLED_FOR_PREMATURE_SIGNAL
            and c_util is not None
            and c_util < _SPARSE_CONTD_UTIL_THRESHOLD
        )
        if not sparse_contd:
            continue

        main_not_full = (
            main_util is not None and main_util < _MAIN_NOT_FULL_UTIL_THRESHOLD
        )
        main_has_internal_slack = (
            main_waste is not None and main_waste > dense_waste_max
        )

        if main_not_full or main_has_internal_slack:
            return True, (
                f"HL (Contd…) slide {contd.get('slide_index')} has only {c_filled} "
                f"filled paragraphs in an oversized HL box while main slide "
                f"{main.get('slide_index')} was not fully utilized "
                f"({main_util:.0%} effective utilization"
                + (
                    f", {main_waste} in slack inside HL box"
                    if main_waste is not None
                    else ""
                )
                + ")."
            )

    return False, ""


def build_cross_slide_hl_context(
    slide: dict[str, Any],
    *,
    main: dict[str, Any] | None,
    contd_hl_slides: list[dict[str, Any]],
    thresholds: TemplateLayoutThresholds | None = None,
) -> dict[str, Any]:
    """Per-slide cross-slide HL context passed to the visual reviewer."""
    thresholds = thresholds or load_thresholds()
    idx = int(slide["slide_index"])
    contd_with_hl = _contd_hl_slides_with_content(contd_hl_slides)

    premature = False
    premature_reason = ""
    if main is not None:
        premature, premature_reason = detect_premature_hl_continuation(
            main, contd_hl_slides, thresholds
        )

    role = "other"
    if main is not None and int(main["slide_index"]) == idx:
        role = "main"
    elif any(int(s["slide_index"]) == idx for s in contd_hl_slides):
        role = "contd_hl"

    main_hl = (main or {}).get("highlights") or {}
    main_util = _hl_effective_util(main) if main else None

    contd_summaries = []
    for contd in contd_hl_slides:
        chl = contd.get("highlights") or {}
        contd_summaries.append({
            "slide_index": contd.get("slide_index"),
            "filled_paragraph_count": chl.get("filled_paragraph_count"),
            "effective_utilization_ratio": _hl_effective_util(contd),
            "hl_waste_below_text_in": contd.get("hl_waste_below_text_in"),
        })

    return {
        "role": role,
        "main_slide_index": main.get("slide_index") if main else None,
        "main_hl_effective_utilization": main_util,
        "main_hl_filled_paragraphs": main_hl.get("filled_paragraph_count"),
        "main_hl_waste_below_text_in": (main or {}).get("hl_waste_below_text_in"),
        "main_hl_room_below_table_in": (
            _hl_room_below_table_to_footer(main) if main else None
        ),
        "main_hl_below_dense_fill": (
            main_util is not None
            and main_util < thresholds.hl_dense_fill_min_effective_util
        ),
        "main_hl_at_capacity": _main_hl_at_capacity(main_util),
        "contd_hl_slides": contd_summaries,
        "has_contd_hl_content": bool(contd_with_hl),
        "premature_hl_continuation_likely": premature,
        "premature_hl_continuation_reason": premature_reason,
        "contd_hl_oversized": (
            _contd_hl_oversized(slide, thresholds) if role == "contd_hl" else False
        ),
        "contd_hl_waste_limit_in": thresholds.hl_waste_contd_hl_max_in,
        "mandatory_check": (
            "Before scoring OK, verify whether HL overflow on (Contd…) was necessary. "
            "If main_hl_at_capacity is true (effective utilization ≥ 100%), NEVER flag "
            "premature_hl_continuation — the main slide is full. Only flag when "
            "main_hl_below_dense_fill is true or main has excess slack inside the HL box. "
            "On contd_hl slides: if contd_hl_oversized is true or hl_waste_below_text_in "
            f"exceeds {thresholds.hl_waste_contd_hl_max_in} in, flag hl_oversized_for_content "
            "on THIS slide (shrink the HL table) even when continuation was justified."
        ),
    }


def build_premature_hl_continuation_issue(
    main: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "category": "premature_hl_continuation",
        "severity": "medium",
        "confidence": 0.95,
        "description": reason,
        "source": "cross_slide_hl_check",
        "flag_slide_index": main.get("slide_index"),
    }


def build_continuation_slide_suggestion(
    main: dict[str, Any],
    *,
    reason: str = "",
) -> dict[str, Any]:
    """Low-priority content-organization hint — never a formatting failure."""
    main_idx = main.get("slide_index")
    message = (
        "This continuation slide contains very little Highlights content. "
        "Consider merging it with the previous slide if appropriate."
    )
    return {
        "type": "content_organization",
        "priority": "low",
        "slide_index": main_idx,
        "message": message,
        "detail": reason,
        "source": "cross_slide_hl_check",
    }


def supplement_premature_hl_continuation_issues(
    deck_slides: list[dict[str, Any]],
    *,
    thresholds: TemplateLayoutThresholds | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """
    Deterministic cross-slide HL continuation findings for visual review.

    Returns issues keyed by slide index (always the MAIN slide index).
    """
    from app.services.ppt_format_violations import _service_base_title

    thresholds = thresholds or load_thresholds()
    by_service: dict[str, dict[str, Any]] = {}
    for slide in deck_slides:
        base = _service_base_title(slide.get("title", ""))
        bucket = by_service.setdefault(
            base, {"main": None, "contd_hl": []}
        )
        if slide.get("is_contd") and slide.get("highlights"):
            if slide.get("layout_type") != "ka_only_contd":
                bucket["contd_hl"].append(slide)
        elif not slide.get("is_contd"):
            bucket["main"] = slide

    issues_by_slide: dict[int, list[dict[str, Any]]] = {}
    for pair in by_service.values():
        main = pair.get("main")
        contd_hl = pair.get("contd_hl") or []
        if not main:
            continue
        likely, reason = detect_premature_hl_continuation(
            main, contd_hl, thresholds
        )
        if likely and reason:
            main_idx = int(main["slide_index"])
            issues_by_slide.setdefault(main_idx, []).append(
                build_premature_hl_continuation_issue(main, reason)
            )

    return issues_by_slide


def build_contd_hl_waste_issue(
    slide: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds,
) -> dict[str, Any]:
    waste = slide.get("hl_waste_below_text_in")
    limit = thresholds.hl_waste_contd_hl_max_in
    waste_s = f"{waste} in" if waste is not None else "excess"
    return {
        "category": "hl_oversized_for_content",
        "severity": "medium",
        "confidence": 0.95,
        "description": (
            f"HL (Contd…) gray box has {waste_s} empty below the last bullet "
            f"(limit {limit} in). Shrink the Highlights table height on this "
            "continuation slide to fit the overflow content — even when the main "
            "slide was at capacity."
        ),
        "source": "contd_hl_waste_check",
        "flag_slide_index": slide.get("slide_index"),
    }


def supplement_contd_hl_waste_issues(
    deck_slides: list[dict[str, Any]],
    *,
    thresholds: TemplateLayoutThresholds | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """
    Flag continuation HL slides with excessive internal waste on the contd slide itself.

    Applies even when the main slide was full — the fix is a smaller HL box on contd.
    """
    thresholds = thresholds or load_thresholds()
    issues_by_slide: dict[int, list[dict[str, Any]]] = {}
    for slide in deck_slides:
        if not _contd_hl_oversized(slide, thresholds):
            continue
        idx = int(slide["slide_index"])
        issues_by_slide.setdefault(idx, []).append(
            build_contd_hl_waste_issue(slide, thresholds=thresholds)
        )
    return issues_by_slide


def supplement_continuation_suggestions(
    deck_slides: list[dict[str, Any]],
    *,
    thresholds: TemplateLayoutThresholds | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """
    Content-organization suggestions for premature HL continuation.

    These do not affect pass/fail scoring.
    """
    from app.services.ppt_format_violations import _service_base_title

    thresholds = thresholds or load_thresholds()
    by_service: dict[str, dict[str, Any]] = {}
    for slide in deck_slides:
        base = _service_base_title(slide.get("title", ""))
        bucket = by_service.setdefault(base, {"main": None, "contd_hl": []})
        if slide.get("is_contd") and slide.get("highlights"):
            if slide.get("layout_type") != "ka_only_contd":
                bucket["contd_hl"].append(slide)
        elif not slide.get("is_contd"):
            bucket["main"] = slide

    suggestions_by_slide: dict[int, list[dict[str, Any]]] = {}
    for pair in by_service.values():
        main = pair.get("main")
        contd_hl = pair.get("contd_hl") or []
        if not main:
            continue
        likely, reason = detect_premature_hl_continuation(
            main, contd_hl, thresholds
        )
        if likely and reason:
            main_idx = int(main["slide_index"])
            suggestions_by_slide.setdefault(main_idx, []).append(
                build_continuation_slide_suggestion(main, reason=reason)
            )
    return suggestions_by_slide
