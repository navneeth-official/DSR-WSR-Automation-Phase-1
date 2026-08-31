"""Derived geometry metrics for qualitative-issue mapping."""

from __future__ import annotations

from typing import Any

from app.services.ppt_layout_metrics import (
    FOOTER_MAX_BOTTOM_IN,
    HL_KA_MAX_BORDER_GAP_IN,
    SPARSE_HL_MAX_WASTE_IN,
    SPARSE_KA_MAX_WASTE_IN,
)

# Vision-aligned thresholds (geometry-side, not pixels).
BELOW_KA_FOOTER_WASTE_IN = 0.85
HL_WASTE_SOFT_IN = 0.15
KA_WASTE_SOFT_IN = 0.25
HL_KA_GAP_SOFT_IN = HL_KA_MAX_BORDER_GAP_IN

TRACKED_METRIC_KEYS = (
    "text_ka_clearance_in",
    "hl_ka_gap_in",
    "hl_waste_below_text_in",
    "ka_waste_below_text_in",
    "below_ka_footer_waste_in",
    "hl_position_in",
    "ka_position_in",
)


def enrich_slide_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Add derived metrics used for qualitative → geometry mapping."""
    out = dict(metrics)
    ka_pos = metrics.get("ka_position_in") or {}
    ka_bottom = ka_pos.get("bottom")
    if ka_bottom is not None:
        out["below_ka_footer_waste_in"] = round(
            max(FOOTER_MAX_BOTTOM_IN - float(ka_bottom), 0.0),
            4,
        )
    return out


def slide_metric_snapshot(slide_metrics: dict[str, Any]) -> dict[str, Any]:
    """Compact before/after comparison dict for one slide."""
    enriched = enrich_slide_metrics(slide_metrics)
    snap: dict[str, Any] = {}
    for key in TRACKED_METRIC_KEYS:
        if key in enriched:
            snap[key] = enriched[key]
    return snap


def metrics_changed(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    min_delta_in: float = 0.01,
) -> bool:
    """True when any tracked scalar metric moved by at least min_delta_in."""
    b = slide_metric_snapshot(before)
    a = slide_metric_snapshot(after)
    for key in TRACKED_METRIC_KEYS:
        if key in ("hl_position_in", "ka_position_in"):
            continue
        bv, av = b.get(key), a.get(key)
        if bv is None or av is None:
            continue
        if abs(float(av) - float(bv)) >= min_delta_in:
            return True
    return _position_changed(b.get("hl_position_in"), a.get("hl_position_in"), min_delta_in) or (
        _position_changed(b.get("ka_position_in"), a.get("ka_position_in"), min_delta_in)
    )


def _position_changed(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    min_delta_in: float,
) -> bool:
    if not before or not after:
        return False
    for field in ("top", "height", "bottom"):
        bv, av = before.get(field), after.get(field)
        if bv is None or av is None:
            continue
        if abs(float(av) - float(bv)) >= min_delta_in:
            return True
    return False


def metric_delta_summary(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, float]:
    """Scalar metric deltas (after − before) for logging."""
    b = slide_metric_snapshot(before)
    a = slide_metric_snapshot(after)
    deltas: dict[str, float] = {}
    for key in TRACKED_METRIC_KEYS:
        if key in ("hl_position_in", "ka_position_in"):
            continue
        bv, av = b.get(key), a.get(key)
        if bv is not None and av is not None:
            deltas[key] = round(float(av) - float(bv), 4)
    return deltas


def qualitative_metric_signals(slide_metrics: dict[str, Any]) -> dict[str, bool]:
    """
    Geometry-side signals that align with qualitative vision categories.

    Used when formal rule violations are absent but vision still flags whitespace.
    """
    m = enrich_slide_metrics(slide_metrics)
    hl_waste = float(m.get("hl_waste_below_text_in") or 0)
    ka_waste = float(m.get("ka_waste_below_text_in") or 0)
    below_ka = float(m.get("below_ka_footer_waste_in") or 0)
    hl_ka_gap = m.get("hl_ka_gap_in")
    gap = float(hl_ka_gap) if hl_ka_gap is not None else 0.0

    return {
        "hl_internal_waste": hl_waste > HL_WASTE_SOFT_IN,
        "hl_sparse_rule": hl_waste > SPARSE_HL_MAX_WASTE_IN,
        "ka_internal_waste": ka_waste > KA_WASTE_SOFT_IN,
        "ka_sparse_rule": ka_waste > SPARSE_KA_MAX_WASTE_IN,
        "below_ka_footer_waste": below_ka > BELOW_KA_FOOTER_WASTE_IN,
        "excessive_hl_ka_gap": gap > HL_KA_GAP_SOFT_IN,
    }


def live_slide_metrics(slide, uds, g10x_prs) -> dict[str, Any]:
    """Read current EMU-derived metrics from an in-memory slide."""
    from app.services.ppt_format_repair import _g10x_ref_for_slide
    from app.services.ppt_layout_metrics import (
        EMU_PER_INCH,
        hl_waste_below_text_in,
        ka_waste_below_text_in,
        text_ka_clearance_in,
    )

    g10x_layout = _g10x_ref_for_slide(uds, g10x_prs, slide)
    profile = uds.build_layout_profile(g10x_layout)
    ref_para = profile.get("ref_para_count", 15)
    ref_r2 = profile.get("ref_r2")

    metrics: dict[str, Any] = {}
    hl = uds.get_highlights_shape(slide)
    ka = uds.get_key_activities_shape(slide)

    if hl:
        metrics["hl_position_in"] = {
            "top": round(hl.top / EMU_PER_INCH, 4),
            "height": round(hl.height / EMU_PER_INCH, 4),
            "bottom": round((hl.top + hl.height) / EMU_PER_INCH, 4),
        }
        metrics["hl_waste_below_text_in"] = hl_waste_below_text_in(
            hl, ref_para_count=ref_para, ref_r2=ref_r2
        )

    if ka:
        metrics["ka_position_in"] = {
            "top": round(ka.top / EMU_PER_INCH, 4),
            "height": round(ka.height / EMU_PER_INCH, 4),
            "bottom": round((ka.top + ka.height) / EMU_PER_INCH, 4),
        }
        metrics["ka_waste_below_text_in"] = ka_waste_below_text_in(ka)

    if hl and ka:
        clearance = text_ka_clearance_in(
            hl, ka, ref_para_count=ref_para, ref_r2=ref_r2
        )
        if clearance is not None:
            metrics["text_ka_clearance_in"] = clearance
        hl_bottom = hl.top + hl.height
        metrics["hl_ka_gap_in"] = round((ka.top - hl_bottom) / EMU_PER_INCH, 4)

    return enrich_slide_metrics(metrics)


def category_supported_by_metrics(category: str, slide_metrics: dict[str, Any]) -> bool:
    """Whether derived metrics support a qualitative category (confidence gating)."""
    signals = qualitative_metric_signals(slide_metrics)
    if category == "excessive_whitespace":
        return any(
            (
                signals["hl_internal_waste"],
                signals["ka_internal_waste"],
                signals["below_ka_footer_waste"],
                signals["excessive_hl_ka_gap"],
            )
        )
    if category == "poor_visual_balance":
        return any(
            (
                signals["below_ka_footer_waste"],
                signals["excessive_hl_ka_gap"],
                signals["hl_internal_waste"],
                signals["ka_internal_waste"],
            )
        )
    if category == "overlap":
        clearance = slide_metrics.get("text_ka_clearance_in")
        return clearance is not None and float(clearance) < 0.15
    if category == "unreadable_layout":
        ka_pos = slide_metrics.get("ka_position_in") or {}
        ka_bottom = ka_pos.get("bottom")
        return ka_bottom is not None and float(ka_bottom) > FOOTER_MAX_BOTTOM_IN
    return False
