"""Slide metadata passed to visual quality review alongside rendered images."""

from __future__ import annotations

from typing import Any

from app.services.ppt_hl_typography import summarize_hl_typography
from app.services.ppt_format_violations import _service_base_title
from app.services.template_calibration import TemplateLayoutThresholds, load_thresholds
from app.vision.cross_slide_hl import build_cross_slide_hl_context


def build_vision_slide_context(
    slide: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds | None = None,
    deterministic_violations: list[dict[str, Any]] | None = None,
    cross_slide_hl: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Compact layout context for the visual reviewer.

    Metrics are pre-computed by deterministic extraction — the AI must not re-measure them.
    """
    thresholds = thresholds or load_thresholds()
    hl = slide.get("highlights") or {}
    ka = slide.get("key_activities")

    layout_metrics: dict[str, Any] = {
        "hl_waste_below_text_in": slide.get("hl_waste_below_text_in"),
        "hl_text_bounds_method": slide.get("hl_text_bounds_method"),
        "rendered_text_bottom_in": slide.get("rendered_text_bottom_in"),
        "hl_ka_gap_in": slide.get("hl_ka_gap_in"),
        "text_ka_clearance_in": slide.get("text_ka_clearance_in"),
        "hl_text_overflow_in": slide.get("hl_text_overflow_in"),
        "ka_waste_below_text_in": slide.get("ka_waste_below_text_in"),
        "estimated_text_bottom_in": slide.get("estimated_text_bottom_in"),
        "ka_rendered_text_bottom_in": slide.get("ka_rendered_text_bottom_in"),
        "highlights_utilization_ratio": hl.get("utilization_ratio"),
        "highlights_effective_utilization_ratio": hl.get("effective_utilization_ratio"),
        "highlights_filled_paragraphs": hl.get("filled_paragraph_count"),
        "highlights_visual_line_count": hl.get("visual_line_count"),
        "key_activities_item_count": ka.get("item_count") if ka else None,
        "footer_content_max_bottom_in": thresholds.footer_content_max_bottom_in,
    }
    if hl:
        layout_metrics["hl_typography"] = summarize_hl_typography(hl)
    if deterministic_violations:
        layout_metrics["deterministic_violations"] = [
            {
                "rule_id": v.get("rule_id"),
                "severity": v.get("severity"),
                "message": v.get("message"),
            }
            for v in deterministic_violations
        ]

    ka_items = ka.get("item_count") if ka else None
    layout_type = slide.get("layout_type")
    review_policy = {
        "empty_key_activities_is_valid": True,
        "key_activities_manual_entry": True,
        "do_not_penalize_empty_ka": True,
        "ka_only_contd_is_valid": layout_type == "ka_only_contd",
    }

    ctx: dict[str, Any] = {
        "title": slide.get("title", ""),
        "is_contd": bool(slide.get("is_contd")),
        "layout_type": layout_type,
        "has_key_activities_section": ka is not None,
        "key_activities_item_count": ka_items,
        "review_policy": review_policy,
        "layout_metrics": layout_metrics,
    }
    if cross_slide_hl is not None:
        ctx["cross_slide_hl"] = cross_slide_hl
    return ctx


def _service_chains_by_title(slides: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_service: dict[str, dict[str, Any]] = {}
    for slide in slides:
        base = _service_base_title(slide.get("title", ""))
        bucket = by_service.setdefault(base, {"main": None, "contd_hl": []})
        if slide.get("is_contd") and slide.get("highlights"):
            if slide.get("layout_type") != "ka_only_contd":
                bucket["contd_hl"].append(slide)
        elif not slide.get("is_contd"):
            bucket["main"] = slide
    return by_service


def build_vision_context_by_slide(
    deck_data: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds | None = None,
    violations_by_slide: dict[int, list[dict[str, Any]]] | None = None,
) -> dict[int, dict[str, Any]]:
    thresholds = thresholds or load_thresholds()
    violations_by_slide = violations_by_slide or {}
    slides = deck_data.get("slides", [])
    chains = _service_chains_by_title(slides)

    contexts: dict[int, dict[str, Any]] = {}
    for slide in slides:
        idx = int(slide["slide_index"])
        base = _service_base_title(slide.get("title", ""))
        chain = chains.get(base, {})
        main = chain.get("main")
        contd_hl = chain.get("contd_hl") or []
        cross_slide = build_cross_slide_hl_context(
            slide,
            main=main,
            contd_hl_slides=contd_hl,
            thresholds=thresholds,
        )
        contexts[idx] = build_vision_slide_context(
            slide,
            thresholds=thresholds,
            deterministic_violations=violations_by_slide.get(idx),
            cross_slide_hl=cross_slide,
        )
    return contexts
