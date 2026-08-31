"""Map geometry violations and qualitative hints to a single repair plan per slide."""

from __future__ import annotations

from app.geometry.metrics import (
    BELOW_KA_FOOTER_WASTE_IN,
    category_supported_by_metrics,
    qualitative_metric_signals,
)
from app.geometry.types import RepairMode, SlideGeometryReport, SlideRepairPlan

# Qualitative categories → geometry rule IDs that confirm the issue.
QUALITATIVE_TO_RULES: dict[str, tuple[str, ...]] = {
    "overlap": ("KA-OVERLAP-01", "KA-PLC-01"),
    "excessive_whitespace": ("HL-SIZE-01", "KA-PLC-02", "KA-SIZE-01"),
    "clipped_text": (),
    "poor_visual_balance": ("KA-PLC-02", "HL-SIZE-01", "KA-SIZE-01"),
    "unreadable_layout": ("GEO-02", "KA-OVERLAP-01"),
    "no_issue": (),
}

# Escalation order when a repair plan produces no measurable geometry change.
REPAIR_ESCALATION: dict[RepairMode, RepairMode] = {
    RepairMode.TIGHTEN_AND_POSITION: RepairMode.COMPACT_VERTICAL,
    RepairMode.SHRINK_HL: RepairMode.COMPACT_VERTICAL,
    RepairMode.SHRINK_KA: RepairMode.COMPACT_VERTICAL,
    RepairMode.COMPACT_VERTICAL: RepairMode.FIX_FOOTER_OVERFLOW,
    RepairMode.ENSURE_CLEARANCE: RepairMode.TIGHTEN_AND_POSITION,
    RepairMode.EXPAND_AND_REFLOW: RepairMode.FIX_FOOTER_OVERFLOW,
    RepairMode.FIX_FOOTER_OVERFLOW: RepairMode.NONE,
}


def _rule_ids(slide: SlideGeometryReport) -> set[str]:
    return {v.rule_id for v in slide.violations}


def _actionable_rules(rules: set[str], slide: SlideGeometryReport) -> set[str]:
    """Filter violations that should not trigger repair (e.g. expected footer-anchored gap)."""
    below_ka = float(slide.metrics.get("below_ka_footer_waste_in") or 99)
    out = set(rules)
    if below_ka < 0.15 and "KA-PLC-02" in out:
        out.discard("KA-PLC-02")
    return out


def qualitative_compatible_with_geometry(category: str, slide: SlideGeometryReport) -> bool:
    """True when geometry rules or derived metrics support the qualitative category."""
    expected = QUALITATIVE_TO_RULES.get(category, ())
    if expected and _rule_ids(slide) & set(expected):
        return True
    return category_supported_by_metrics(category, slide.metrics)


def _plan_for_whitespace(slide: SlideGeometryReport, *, reason: str) -> SlideRepairPlan:
    """Pick one repair for whitespace / balance issues using derived metrics."""
    signals = qualitative_metric_signals(slide.metrics)
    below_ka = float(slide.metrics.get("below_ka_footer_waste_in") or 0)

    if below_ka > BELOW_KA_FOOTER_WASTE_IN or signals["below_ka_footer_waste"]:
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.COMPACT_VERTICAL,
            layout_mode="normal",
            reason=f"{reason} — anchor KA at footer, tighten HL",
            triggered_by=(reason,),
        )

    if signals["ka_internal_waste"] or signals["ka_sparse_rule"]:
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.SHRINK_KA,
            reason=f"{reason} — shrink KA table to item content",
            triggered_by=(reason,),
        )

    if signals["hl_internal_waste"] or signals["hl_sparse_rule"]:
        if below_ka < 0.15:
            return SlideRepairPlan(
                slide_index=slide.slide_index,
                mode=RepairMode.SHRINK_HL,
                reason=f"{reason} — shrink HL only (KA footer anchor preserved)",
                triggered_by=(reason,),
            )
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.TIGHTEN_AND_POSITION,
            layout_mode="normal",
            reason=f"{reason} — tighten HL and close HL–KA gap",
            triggered_by=(reason,),
        )

    if signals["excessive_hl_ka_gap"]:
        if below_ka < 0.15:
            return SlideRepairPlan(
                slide_index=slide.slide_index,
                mode=RepairMode.NONE,
                reason=f"{reason} — HL–KA gap expected with footer-anchored KA",
                triggered_by=(reason,),
            )
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.TIGHTEN_AND_POSITION,
            layout_mode="normal",
            reason=f"{reason} — tighten HL and close HL–KA gap",
            triggered_by=(reason,),
        )

    return SlideRepairPlan(
        slide_index=slide.slide_index,
        mode=RepairMode.NONE,
        reason=f"{reason} — no further geometry adjustment available",
        triggered_by=(reason,),
    )


def escalate_repair_plan(plan: SlideRepairPlan) -> SlideRepairPlan:
    """Return the next repair mode when the prior plan did not change geometry."""
    next_mode = REPAIR_ESCALATION.get(plan.mode, RepairMode.NONE)
    if next_mode == RepairMode.NONE:
        return SlideRepairPlan(
            slide_index=plan.slide_index,
            mode=RepairMode.NONE,
            reason=f"No further escalation after {plan.mode.value}",
            triggered_by=plan.triggered_by,
        )
    return SlideRepairPlan(
        slide_index=plan.slide_index,
        mode=next_mode,
        layout_mode=plan.layout_mode,
        expand_for_wrap=plan.expand_for_wrap,
        reason=f"Escalated from {plan.mode.value}",
        triggered_by=plan.triggered_by,
    )


def plan_slide_repair(
    slide: SlideGeometryReport,
    *,
    qualitative_categories: tuple[str, ...] = (),
    allow_qualitative_only: bool = False,
) -> SlideRepairPlan:
    """
    Compute one coherent repair plan for a slide.

    Conflicting micro-actions are avoided by delegating to a single repair mode.
    """
    rules = _rule_ids(slide)
    actionable = _actionable_rules(rules, slide)
    triggers = tuple(sorted(rules | set(qualitative_categories)))

    if not actionable and not allow_qualitative_only:
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.NONE,
            reason="No geometry violations",
            triggered_by=triggers,
        )

    # Footer overflow: move KA up — never expand HL (prior bug).
    if "GEO-02" in actionable:
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.FIX_FOOTER_OVERFLOW,
            reason="Footer safe-zone overflow — shrink and raise KA",
            triggered_by=triggers,
        )

    # True text overlap — expand HL for wrap clearance only when clearance is low.
    clearance = slide.metrics.get("text_ka_clearance_in")
    if actionable & {"KA-OVERLAP-01", "KA-PLC-01"}:
        if clearance is not None and float(clearance) < 0.05:
            # Tighten to content + table-border gap; avoid expanded HL that pushes KA into footer.
            return SlideRepairPlan(
                slide_index=slide.slide_index,
                mode=RepairMode.TIGHTEN_AND_POSITION,
                layout_mode="normal",
                reason="Critical text–KA clearance",
                triggered_by=triggers,
            )
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.TIGHTEN_AND_POSITION,
            layout_mode="normal",
            reason="Text–KA clearance — tighten and reposition",
            triggered_by=triggers,
        )

    if actionable & {"HL-SIZE-01", "KA-SIZE-01", "CONT-SPARSE-01"}:
        below_ka = float(slide.metrics.get("below_ka_footer_waste_in") or 99)
        if "KA-SIZE-01" in rules:
            return SlideRepairPlan(
                slide_index=slide.slide_index,
                mode=RepairMode.SHRINK_KA,
                reason="Sparse content — shrink KA table",
                triggered_by=triggers,
            )
        if "HL-SIZE-01" in rules and below_ka < 0.15:
            return SlideRepairPlan(
                slide_index=slide.slide_index,
                mode=RepairMode.SHRINK_HL,
                reason="Shrink HL only — preserve KA footer anchor",
                triggered_by=triggers,
            )
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.TIGHTEN_AND_POSITION,
            layout_mode="normal",
            reason="Sparse content / excessive HL box size",
            triggered_by=triggers,
        )

    if "KA-PLC-02" in rules:
        below_ka = float(slide.metrics.get("below_ka_footer_waste_in") or 99)
        if below_ka >= 0.15:
            return SlideRepairPlan(
                slide_index=slide.slide_index,
                mode=RepairMode.TIGHTEN_AND_POSITION,
                layout_mode="normal",
                reason="Excessive HL–KA border gap",
                triggered_by=triggers,
            )

    # Qualitative-only path (high confidence or metric-confirmed).
    if allow_qualitative_only and qualitative_categories:
        for category in qualitative_categories:
            if category in ("excessive_whitespace", "poor_visual_balance"):
                return _plan_for_whitespace(
                    slide,
                    reason=f"Qualitative issue: {category}",
                )
            if category == "overlap":
                return SlideRepairPlan(
                    slide_index=slide.slide_index,
                    mode=RepairMode.TIGHTEN_AND_POSITION,
                    layout_mode="normal",
                    reason=f"Qualitative issue: {category}",
                    triggered_by=triggers,
                )
            if category == "unreadable_layout":
                return SlideRepairPlan(
                    slide_index=slide.slide_index,
                    mode=RepairMode.FIX_FOOTER_OVERFLOW,
                    reason=f"Qualitative issue: {category}",
                    triggered_by=triggers,
                )

    if actionable:
        return SlideRepairPlan(
            slide_index=slide.slide_index,
            mode=RepairMode.TIGHTEN_AND_POSITION,
            layout_mode="normal",
            reason="General layout repair",
            triggered_by=triggers,
        )

    return SlideRepairPlan(
        slide_index=slide.slide_index,
        mode=RepairMode.NONE,
        reason="No applicable repair",
        triggered_by=triggers,
    )
