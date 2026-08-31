"""Hybrid validation loop: geometry inspect/correct → render → qualitative vision."""

from __future__ import annotations

from pathlib import Path

from app.geometry.confidence import (
    categories_for_correction,
    gate_qualitative_issue,
    requires_manual_review,
)
from app.geometry.corrector import GeometryCorrector
from app.geometry.inspector import GeometryInspector
from app.geometry.metrics import metrics_changed, slide_metric_snapshot
from app.geometry.planner import escalate_repair_plan, plan_slide_repair
from app.geometry.types import SlideRepairPlan
from app.pipeline.protocols import DeckGenerator, PptRenderer
from app.pipeline.qualitative_reviewer import QualitativeVisionReviewer
from app.pipeline.types import HybridLoopIteration, HybridValidationResult, PipelineConfig


class HybridValidationLoop:
    """
    Geometry-first validation with qualitative vision review.

    Per iteration
    -------------
    1. Geometry inspection (PPTX EMU — authoritative measurements)
    2. Geometry correction — one coherent plan per slide (no conflicting actions)
    3. Verify each correction changed measurable geometry before continuing
    4. Render slides to PNG
    5. Qualitative vision review (no pixel values)
    6. Confidence-gate qualitative issues; escalate noop plans next iteration
    """

    def __init__(
        self,
        *,
        renderer: PptRenderer,
        qualitative_reviewer: QualitativeVisionReviewer,
        geometry_inspector: GeometryInspector | None = None,
        geometry_corrector: GeometryCorrector | None = None,
        deck_generator: DeckGenerator | None = None,
    ) -> None:
        self._renderer = renderer
        self._reviewer = qualitative_reviewer
        self._inspector = geometry_inspector or GeometryInspector()
        self._corrector = geometry_corrector or GeometryCorrector()
        self._deck_generator = deck_generator

    def run(
        self,
        ppt_path: Path | None = None,
        *,
        content_json: Path | None = None,
        output_ppt: Path | None = None,
        layout_hints: Path | None = None,
        config: PipelineConfig | None = None,
    ) -> HybridValidationResult:
        cfg = config or PipelineConfig()
        ppt_path = self._resolve_ppt_path(
            ppt_path,
            content_json=content_json,
            output_ppt=output_ppt,
            layout_hints=layout_hints,
        )

        iterations: list[HybridLoopIteration] = []
        all_manual_review: list[dict] = []
        pending_qual_plans: dict[int, SlideRepairPlan] = {}
        failed_plans: dict[int, SlideRepairPlan] = {}
        final_geo: dict | None = None
        final_qual: dict | None = None
        stopped_reason = "iteration_limit"

        for round_num in range(1, cfg.max_iterations + 1):
            geo_report = self._inspector.inspect(ppt_path)
            pre_metrics = {
                s.slide_index: slide_metric_snapshot(s.metrics)
                for s in geo_report.slides
            }
            final_geo = geo_report.to_dict()

            slide_plans: dict[int, SlideRepairPlan] = dict(pending_qual_plans)
            pending_qual_plans = {}

            for slide in geo_report.slides:
                idx = slide.slide_index
                if slide.has_violations:
                    slide_plans[idx] = plan_slide_repair(slide)
                elif idx in failed_plans:
                    escalated = escalate_repair_plan(failed_plans[idx])
                    if escalated.applies_change:
                        slide_plans[idx] = escalated

            geo_correction = None
            if slide_plans:
                correction = self._corrector.correct(
                    ppt_path,
                    geo_report,
                    slide_plans=slide_plans,
                    save=True,
                )
                geo_correction = correction.to_dict()

                post_report = self._inspector.inspect(ppt_path)
                final_geo = post_report.to_dict()
                geo_by_idx = {s.slide_index: s for s in post_report.slides}

                failed_plans = {}
                for delta in correction.slide_deltas:
                    idx = delta.slide_index
                    if delta.changed:
                        continue
                    plan = slide_plans.get(idx)
                    if plan is None:
                        continue
                    escalated = escalate_repair_plan(plan)
                    if escalated.applies_change:
                        failed_plans[idx] = plan
                        pending_qual_plans[idx] = escalated

                for idx in correction.slides_modified:
                    before = pre_metrics.get(idx, {})
                    after_slide = geo_by_idx.get(idx)
                    if after_slide is None:
                        continue
                    after = slide_metric_snapshot(after_slide.metrics)
                    if not metrics_changed(before, after):
                        plan = slide_plans.get(idx)
                        if plan:
                            escalated = escalate_repair_plan(plan)
                            if escalated.applies_change:
                                failed_plans[idx] = plan
                                pending_qual_plans[idx] = escalated

                geo_report = post_report

            render_batch = self._renderer.render_deck(
                ppt_path,
                output_dir=cfg.render_output_dir,
                keep_images=cfg.keep_render_images,
            )

            qual_report = self._reviewer.evaluate(render_batch)
            final_qual = qual_report.to_dict()

            qual_by_slide = {(s.slide_number or 0): s for s in qual_report.slides}
            geo_by_slide = {s.slide_index: s for s in geo_report.slides}
            manual_this_round: list[dict] = []

            for slide_idx, qual_slide in qual_by_slide.items():
                if slide_idx <= 0:
                    continue
                geo_slide = geo_by_slide.get(slide_idx)
                if geo_slide is None:
                    continue

                gated = [
                    gate_qualitative_issue(issue.to_dict(), geo_slide)
                    for issue in qual_slide.issues
                ]
                cats = categories_for_correction(gated)
                high_conf_only = any(
                    g.allow_correction and g.gate_reason == "high_confidence"
                    for g in gated
                )
                medium_confirmed = any(
                    g.allow_correction
                    and g.gate_reason == "medium_confidence_with_geometry_confirmation"
                    for g in gated
                )

                if cats and (high_conf_only or medium_confirmed):
                    plan = plan_slide_repair(
                        geo_slide,
                        qualitative_categories=cats,
                        allow_qualitative_only=high_conf_only or medium_confirmed,
                    )
                    if plan.applies_change:
                        pending_qual_plans[slide_idx] = plan

                needs_review, reasons = requires_manual_review(
                    gated,
                    geo_slide,
                    correction_applied=bool(
                        geo_correction
                        and slide_idx in geo_correction.get("slides_modified", [])
                    ),
                )
                if needs_review:
                    entry = {
                        "slide_index": slide_idx,
                        "title": geo_slide.title,
                        "reasons": reasons,
                    }
                    manual_this_round.append(entry)
                    all_manual_review.append(entry)

            iterations.append(
                HybridLoopIteration(
                    iteration=round_num,
                    geometry_report=final_geo or {},
                    geometry_correction=geo_correction,
                    render_batch=render_batch.to_metadata(),
                    qualitative_report=final_qual or {},
                    manual_review_slides=manual_this_round,
                )
            )

            if (
                geo_report.passes
                and self._reviewer.passes(qual_report)
                and not manual_this_round
                and not pending_qual_plans
                and not failed_plans
            ):
                return HybridValidationResult(
                    ppt_path=ppt_path,
                    passed=True,
                    stopped_reason="all_checks_passed",
                    iterations=iterations,
                    final_geometry_report=final_geo,
                    final_qualitative_report=final_qual,
                    manual_review_slides=all_manual_review,
                )

            if (
                not geo_correction
                and not pending_qual_plans
                and not failed_plans
            ):
                if not geo_report.passes:
                    stopped_reason = "geometry_violations_remain"
                elif manual_this_round:
                    stopped_reason = "manual_review_required"
                else:
                    stopped_reason = "qualitative_review_incomplete"
                if round_num >= cfg.max_iterations:
                    stopped_reason = "iteration_limit"
                break

        return HybridValidationResult(
            ppt_path=ppt_path,
            passed=False,
            stopped_reason=stopped_reason,
            iterations=iterations,
            final_geometry_report=final_geo,
            final_qualitative_report=final_qual,
            manual_review_slides=all_manual_review,
        )

    def _resolve_ppt_path(
        self,
        ppt_path: Path | None,
        *,
        content_json: Path | None,
        output_ppt: Path | None,
        layout_hints: Path | None,
    ) -> Path:
        if content_json is not None and output_ppt is not None:
            if self._deck_generator is None:
                raise ValueError("Deck generation requested but no DeckGenerator injected.")
            return self._deck_generator.generate(
                content_json,
                output_ppt,
                layout_hints=layout_hints,
            ).resolve()
        if ppt_path is None:
            raise ValueError("Provide ppt_path or both content_json and output_ppt.")
        return ppt_path.resolve()
