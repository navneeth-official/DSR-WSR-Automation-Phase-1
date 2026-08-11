"""Deterministic spacing/layout violation detection for delivery-status slides.

Rules follow visual-principles evaluation calibrated from the G10X WSR template:
overlap and clipping are geometry-based on rendered content; whitespace and box
height variations within template bands are acceptable.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.ppt_hl_typography import detect_hl_typography_violations
from app.services.ppt_layout_metrics import (
    DEFAULT_EMPTY_KA_HEIGHT_IN,
    HL_KA_TARGET_BORDER_GAP_IN,
)
from app.services.template_calibration import TemplateLayoutThresholds, load_thresholds
from app.services.template_typography import TemplateTypographySpec


def _service_base_title(title: str) -> str:
    base = re.sub(r"^Delivery status\s*[–-]\s*", "", title, flags=re.I)
    return re.sub(r"\s*\(Contd.*\)\s*$", "", base, flags=re.I).strip()


def _hl_effective_util(hl: dict[str, Any]) -> float | None:
    util = hl.get("effective_utilization_ratio", hl.get("utilization_ratio"))
    return float(util) if util is not None else None


def _is_hl_dense_fill(hl: dict[str, Any], thresholds: TemplateLayoutThresholds) -> bool:
    util = _hl_effective_util(hl)
    return (
        util is not None
        and util >= thresholds.hl_dense_fill_min_effective_util
    )


def _is_contd_hl_slide(slide: dict[str, Any]) -> bool:
    """HL overflow continuation slide (not KA-only contd)."""
    if not slide.get("is_contd") or not slide.get("highlights"):
        return False
    return slide.get("layout_type") != "ka_only_contd"


def _contd_hl_oversized(
    slide: dict[str, Any],
    thresholds: TemplateLayoutThresholds,
) -> bool:
    """
    Continuation HL slide keeps the main-slide gray box height while carrying
    sparse overflow — flag when internal waste exceeds the tight contd band.
    """
    if not _is_contd_hl_slide(slide):
        return False
    waste = slide.get("hl_waste_below_text_in")
    if waste is None:
        return False
    return float(waste) > thresholds.hl_waste_contd_hl_max_in


def _hl_room_below_table_to_footer(slide: dict[str, Any]) -> float | None:
    """White space on slide below the HL table border (not inside the gray box)."""
    bottom = slide.get("hl_bottom_measured_in")
    if bottom is None:
        hl = slide.get("highlights") or {}
        bottom = hl.get("position_in", {}).get("bottom")
    if bottom is None:
        return None
    limit = load_thresholds().footer_content_max_bottom_in
    return round(max(limit - float(bottom), 0), 4)


def _hl_waste_limit(
    slide: dict[str, Any],
    thresholds: TemplateLayoutThresholds,
) -> float:
    """
    Calibrated internal-waste band from measured layout, not slide labels.

    Dense-fill slides (high effective utilization) use a tight band.
    Sparse HL with a Key Activities section uses the wider template band.
    Continuation HL slides use the relaxed contd band.
    """
    if _is_contd_hl_slide(slide):
        return thresholds.hl_waste_contd_hl_max_in
    hl = slide.get("highlights") or {}
    if _is_hl_dense_fill(hl, thresholds):
        return thresholds.hl_waste_dense_fill_max_in
    if slide.get("key_activities") is not None:
        return thresholds.hl_waste_sparse_ka_max_in
    return thresholds.hl_waste_dense_fill_max_in


def _excessive_hl_ka_spacing(
    slide: dict[str, Any],
    thresholds: TemplateLayoutThresholds,
) -> str | None:
    """
    HL table bottom → KA header gap (the double-arrow spacing).

    Sustainment decks place KA at HL_KA_TARGET_BORDER_GAP_IN (~0.472 in, two
    body lines). Use the builder target when it exceeds the calibrated JSON band.
    """
    if slide.get("key_activities") is None:
        return None
    gap = slide.get("hl_ka_gap_in")
    if gap is None:
        return None
    target = max(thresholds.hl_ka_border_gap_target_in, HL_KA_TARGET_BORDER_GAP_IN)
    max_gap = max(
        thresholds.hl_ka_border_gap_max_in,
        round(HL_KA_TARGET_BORDER_GAP_IN + 0.03, 4),
    )
    if gap > max_gap:
        return (
            f"HL table bottom to KA header gap {gap} in exceeds template "
            f"~{target:.2f} in (max {max_gap:.2f} in, ~2 body lines)"
        )
    return None


def _hl_internal_waste_excessive(
    slide: dict[str, Any],
    thresholds: TemplateLayoutThresholds,
) -> bool:
    """Empty gray inside HL box below last bullet, above calibrated reference band."""
    waste = slide.get("hl_waste_below_text_in")
    if waste is None:
        return False
    return waste > _hl_waste_limit(slide, thresholds)


def _sparse_hl_with_ka_oversized(
    hl: dict[str, Any],
    slide: dict[str, Any],
    thresholds: TemplateLayoutThresholds,
) -> bool:
    """Sparse HL + KA layout with HL box larger than the approved template band."""
    if _is_contd_hl_slide(slide):
        return False
    if slide.get("key_activities") is None:
        return False
    util = _hl_effective_util(hl)
    if util is None or util >= thresholds.hl_dense_fill_min_effective_util:
        return False
    return _hl_internal_waste_excessive(slide, thresholds)


def compute_service_chains(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-service slide grouping for contextual AI review (not threshold selection)."""
    by_service: dict[str, dict[str, Any]] = {}
    for slide in slides:
        base = _service_base_title(slide.get("title", ""))
        bucket = by_service.setdefault(
            base, {"main": None, "contd_hl": [], "contd_ka_only": None}
        )
        if slide.get("is_contd"):
            if slide.get("layout_type") == "ka_only_contd":
                bucket["contd_ka_only"] = slide
            elif slide.get("highlights"):
                bucket["contd_hl"].append(slide)
        else:
            bucket["main"] = slide

    chains: list[dict[str, Any]] = []
    for service, pair in by_service.items():
        main = pair.get("main")
        if not main:
            continue
        contd_hl = pair.get("contd_hl") or []
        contd_ka = pair.get("contd_ka_only")
        hl = main.get("highlights") or {}
        chain: dict[str, Any] = {
            "service": service,
            "main_slide_index": main.get("slide_index"),
            "main_layout_type": main.get("layout_type"),
            "main_hl_para_util": hl.get("utilization_ratio"),
            "main_hl_effective_util": hl.get("effective_utilization_ratio"),
            "main_hl_visual_lines": hl.get("visual_line_count"),
            "main_hl_waste_below_text_in": main.get("hl_waste_below_text_in"),
            "main_hl_room_below_table_in": _hl_room_below_table_to_footer(main),
            "contd_hl_slide_indices": [s.get("slide_index") for s in contd_hl],
            "ka_only_contd_slide_index": (
                contd_ka.get("slide_index") if contd_ka else None
            ),
        }
        if contd_hl:
            sparsest = min(
                contd_hl,
                key=lambda s: (s.get("highlights") or {}).get(
                    "filled_paragraph_count", 999
                ),
            )
            chl = sparsest.get("highlights") or {}
            chain["sparsest_contd_slide_index"] = sparsest.get("slide_index")
            chain["sparsest_contd_filled_paras"] = chl.get("filled_paragraph_count")
            chain["sparsest_contd_util"] = chl.get("utilization_ratio")
        chains.append(chain)
    return chains


def terminal_slide_indices_for_chains(chains: list[dict[str, Any]]) -> frozenset[int]:
    """Slide index where Key Activities may belong — last slide in each service chain."""
    indices: set[int] = set()
    for chain in chains:
        ka_only = chain.get("ka_only_contd_slide_index")
        if ka_only is not None:
            indices.add(int(ka_only))
            continue
        contd = chain.get("contd_hl_slide_indices") or []
        if contd:
            indices.add(int(max(contd)))
            continue
        main = chain.get("main_slide_index")
        if main is not None:
            indices.add(int(main))
    return frozenset(indices)


def _ka_would_fit_below_hl(
    slide: dict[str, Any],
    thresholds: TemplateLayoutThresholds,
) -> bool:
    """True when an empty KA table fits below HL with typical template clearance."""
    hl = slide.get("highlights") or {}
    hl_bottom = slide.get("hl_bottom_measured_in")
    if hl_bottom is None:
        hl_bottom = hl.get("position_in", {}).get("bottom")
    text_bottom = slide.get("hl_text_bottom_for_fit_in") or slide.get(
        "estimated_text_bottom_in"
    )
    if hl_bottom is not None:
        ka_top = float(hl_bottom) + HL_KA_TARGET_BORDER_GAP_IN
    elif text_bottom is not None:
        ka_top = float(text_bottom) + thresholds.min_text_ka_clearance_in
    else:
        return False
    return ka_top + DEFAULT_EMPTY_KA_HEIGHT_IN <= thresholds.footer_content_max_bottom_in


def _content_enters_footer(slide: dict[str, Any], thresholds: TemplateLayoutThresholds) -> bool:
    """True when rendered HL or KA text extends into the footer reserved region."""
    limit = thresholds.footer_content_max_bottom_in
    hl_text = slide.get("rendered_text_bottom_in") or slide.get("estimated_text_bottom_in")
    if hl_text is not None and hl_text > limit:
        return True
    ka_text = slide.get("ka_rendered_text_bottom_in")
    if ka_text is not None and ka_text > limit:
        return True
    return False


def _hl_visually_unbalanced(hl: dict[str, Any], slide: dict[str, Any], thresholds: TemplateLayoutThresholds) -> bool:
    """
    Extreme stretch only: nearly empty HL box with far more whitespace than the
    template ever uses. Normal intentional slack (e.g. Location) is allowed.
    """
    util = _hl_effective_util(hl)
    if util is None or util >= thresholds.hl_waste_stretch_max_util:
        return False
    waste = slide.get("hl_waste_below_text_in")
    if waste is None:
        return False
    return waste > thresholds.hl_waste_extreme_in


def _ka_visually_unbalanced(ka: dict[str, Any], slide: dict[str, Any], thresholds: TemplateLayoutThresholds) -> bool:
    item_count = ka.get("item_count", 0)
    if item_count == 0:
        return False
    util = ka.get("utilization_ratio")
    if util is None or util >= thresholds.ka_waste_stretch_max_util:
        return False
    waste = slide.get("ka_waste_below_text_in")
    if waste is None:
        return False
    return waste > thresholds.ka_waste_extreme_in


def detect_slide_violations(
    slide: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds | None = None,
    typography: TemplateTypographySpec | None = None,
    ka_placement_terminal_indices: frozenset[int] | None = None,
) -> list[dict[str, Any]]:
    """Return violation dicts for one extracted slide."""
    thresholds = thresholds or load_thresholds()
    violations: list[dict[str, Any]] = []
    idx = slide.get("slide_index")
    title = slide.get("title", "")

    if re.search(r"Delivery status\s+-\s+", title) and not re.search(
        r"Delivery status\s+–\s+", title
    ):
        violations.append({
            "rule_id": "TITLE-01",
            "severity": "major",
            "slide_index": idx,
            "title": title,
            "message": "Slide title uses hyphen '-' instead of en dash '–' after Delivery status",
        })

    hl = slide.get("highlights")
    ka_on_slide = slide.get("key_activities") is not None

    if hl:
        violations.extend(
            detect_hl_typography_violations(
                hl,
                slide_index=idx,
                title=title,
                typography=typography,
            )
        )

        if hl.get("category_bullet_violations"):
            violations.append({
                "rule_id": "HL-P-04",
                "severity": "critical",
                "slide_index": idx,
                "title": title,
                "message": "Category headers use wrong bullet (must be Wingdings Ø at level 7)",
                "details": hl["category_bullet_violations"],
            })

        if hl.get("category_to_story_blank_gaps", 0) > 0:
            violations.append({
                "rule_id": "HL-SPC-01",
                "severity": "major",
                "slide_index": idx,
                "title": title,
                "message": "Blank line between category header and first story (sections merged)",
            })

        clearance = slide.get("text_ka_clearance_in")
        if (
            clearance is not None
            and clearance < thresholds.min_text_ka_clearance_in
            and ka_on_slide
        ):
            violations.append({
                "rule_id": "KA-OVERLAP-01",
                "severity": "critical",
                "slide_index": idx,
                "title": title,
                "message": (
                    f"Highlights text overlaps Key Activities "
                    f"(clearance {clearance} in < {thresholds.min_text_ka_clearance_in} in)"
                ),
            })

        overflow = slide.get("hl_text_overflow_in")
        if (
            overflow is not None
            and overflow > thresholds.hl_text_overflow_tolerance_in
            and ka_on_slide
        ):
            violations.append({
                "rule_id": "HL-OVERFLOW-01",
                "severity": "critical",
                "slide_index": idx,
                "title": title,
                "message": (
                    f"Highlights text extends outside its table "
                    f"({overflow} in past table bottom)"
                ),
            })

        if _hl_visually_unbalanced(hl, slide, thresholds):
            waste = slide.get("hl_waste_below_text_in")
            violations.append({
                "rule_id": "HL-SIZE-01",
                "severity": "major",
                "slide_index": idx,
                "title": title,
                "message": (
                    f"Highlights box excessively stretched for sparse content "
                    f"({waste} in empty below text, above template band)"
                ),
            })

        spacing_msg = _excessive_hl_ka_spacing(slide, thresholds)
        if spacing_msg:
            violations.append({
                "rule_id": "KA-PLC-02",
                "severity": "major",
                "slide_index": idx,
                "title": title,
                "message": spacing_msg,
            })

        if _sparse_hl_with_ka_oversized(hl, slide, thresholds):
            waste = slide.get("hl_waste_below_text_in")
            violations.append({
                "rule_id": "CONT-SPARSE-01",
                "severity": "major",
                "slide_index": idx,
                "title": title,
                "message": (
                    "Sparse Highlights with Key Activities and oversized HL box"
                    + (f" ({waste} in empty below text)" if waste is not None else "")
                ),
            })

        if _contd_hl_oversized(slide, thresholds):
            waste = slide.get("hl_waste_below_text_in")
            limit = thresholds.hl_waste_contd_hl_max_in
            violations.append({
                "rule_id": "CONT-HL-01",
                "severity": "major",
                "slide_index": idx,
                "title": title,
                "message": (
                    "HL (Contd…) box is oversized for sparse overflow content"
                    + (
                        f" ({waste} in empty gray below text, limit {limit} in). "
                        "Shrink the Highlights table height on this continuation slide."
                        if waste is not None
                        else ". Shrink the Highlights table height on this continuation slide."
                    )
                ),
            })

        is_ka_terminal_slide = (
            ka_placement_terminal_indices is None
            or idx in ka_placement_terminal_indices
        )
        if (
            hl
            and not ka_on_slide
            and is_ka_terminal_slide
            and _ka_would_fit_below_hl(slide, thresholds)
        ):
            hl_pos = hl.get("position_in", {})
            hl_bottom = slide.get("hl_bottom_measured_in") or hl_pos.get("bottom")
            text_bottom = slide.get("hl_text_bottom_for_fit_in") or slide.get(
                "estimated_text_bottom_in"
            )
            room_in = (
                round(float(hl_bottom) - float(text_bottom), 4)
                if hl_bottom is not None and text_bottom is not None
                else None
            )
            violations.append({
                "rule_id": "KA-PLC-04",
                "severity": "critical",
                "slide_index": idx,
                "title": title,
                "message": (
                    "Key Activities absent but slide has room to fit HL + KA together"
                    + (f" ({room_in} in below HL text)" if room_in is not None else "")
                ),
            })

    ka = slide.get("key_activities")
    if ka and _ka_visually_unbalanced(ka, slide, thresholds):
        waste = slide.get("ka_waste_below_text_in")
        violations.append({
            "rule_id": "KA-SIZE-01",
            "severity": "major",
            "slide_index": idx,
            "title": title,
            "message": (
                f"Key Activities box excessively stretched for sparse content "
                f"({waste} in empty below items, above template band)"
            ),
        })

    if _content_enters_footer(slide, thresholds):
        hl_text = slide.get("estimated_text_bottom_in")
        ka_text = slide.get("ka_rendered_text_bottom_in")
        violations.append({
            "rule_id": "GEO-02",
            "severity": "critical",
            "slide_index": idx,
            "title": title,
            "message": (
                "Rendered content enters the footer safe zone "
                f"(HL text {hl_text} in, KA text {ka_text} in, "
                f"limit {thresholds.footer_content_max_bottom_in} in)"
            ),
        })

    return violations


def detect_deck_violations(
    deck_data: dict[str, Any],
    *,
    content_titles: set[str] | None = None,
    scope_all_slides: bool = False,
    thresholds: TemplateLayoutThresholds | None = None,
    typography: TemplateTypographySpec | None = None,
) -> dict[str, Any]:
    """Detect violations across deck using per-slide layout measurements."""
    thresholds = thresholds or load_thresholds()
    slides = deck_data.get("slides", [])
    if content_titles is not None and not scope_all_slides:
        allowed = {t.strip().lower() for t in content_titles}

        def in_scope(title: str) -> bool:
            return _service_base_title(title).lower() in allowed

        slides = [s for s in slides if in_scope(s.get("title", ""))]

    all_violations: list[dict[str, Any]] = []
    chains = compute_service_chains(slides)
    ka_terminal = terminal_slide_indices_for_chains(chains)
    for slide in slides:
        all_violations.extend(
            detect_slide_violations(
                slide,
                thresholds=thresholds,
                typography=typography,
                ka_placement_terminal_indices=ka_terminal,
            )
        )

    critical = [v for v in all_violations if v.get("severity") == "critical"]
    return {
        "violation_count": len(all_violations),
        "critical_count": len(critical),
        "violations": all_violations,
        "has_critical": bool(critical),
    }
