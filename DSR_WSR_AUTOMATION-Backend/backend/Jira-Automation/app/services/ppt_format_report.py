"""Unified hybrid PPT evaluation — deterministic geometry + visual AI review."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.pipeline.qualitative_reviewer import QualitativeVisionReviewer
from app.pipeline.types import RenderBatch, RenderedSlide
from app.services.ppt_deterministic_scoring import (
    compute_deck_deterministic_score,
    compute_slide_deterministic_score,
)
from app.services.ppt_format_evaluator import evaluate_deck_format, load_rulebook
from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_violations import compute_service_chains, detect_deck_violations
from app.services.ppt_slide_images import export_slides_to_png, list_delivery_slide_indices
from app.services.ppt_visual_scoring import (
    combine_hybrid_score,
    compute_deck_visual_score,
    compute_visual_score_result,
)
from app.config import llm_configured
from app.vision.cross_slide_hl import (
    supplement_contd_hl_waste_issues,
    supplement_continuation_suggestions,
)
from app.vision.issue_gating import (
    build_service_chain_by_slide,
    filter_vision_issues,
    layout_owns_hl_container_finding,
    resolve_visual_pass_after_gating,
    vision_issues_fail,
)
from app.vision.logging import configure_vision_logging, default_log_path
from app.vision.slide_context import build_vision_context_by_slide

EvaluatorMode = Literal["full", "ai", "deterministic", "visual"]

_FAIL_SEVERITIES = frozenset({"critical", "major"})
_HYBRID_DET_WEIGHT = 0.70
_HYBRID_VIS_WEIGHT = 0.30


def _vision_issues_fail(issues: list[dict[str, Any]]) -> bool:
    return vision_issues_fail(issues)


@dataclass
class SlideFormatResult:
    slide_index: int
    title: str
    passed: bool
    deterministic_pass: bool | None = None
    visual_pass: bool | None = None
    ai_pass: bool | None = None  # legacy rulebook mode only
    deterministic_score: float | None = None
    visual_score: float | None = None
    final_score: float | None = None
    score: float | None = None  # alias for final_score in reports
    category_scores: dict[str, float] = field(default_factory=dict)
    violations: list[dict[str, Any]] = field(default_factory=list)
    visual_issues: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    has_critical_violation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "title": self.title,
            "pass": self.passed,
            "deterministic_pass": self.deterministic_pass,
            "visual_pass": self.visual_pass,
            "ai_pass": self.ai_pass,
            "deterministic_score": self.deterministic_score,
            "visual_score": self.visual_score,
            "final_score": self.final_score,
            "score": self.final_score,
            "category_scores": self.category_scores,
            "violations": self.violations,
            "visual_issues": self.visual_issues,
            "suggestions": self.suggestions,
            "strengths": self.strengths,
            "has_critical_violation": self.has_critical_violation,
        }


@dataclass
class DeckFormatReport:
    source_file: str
    mode: str
    deck_pass: bool
    deck_score: float | None
    deterministic_score: float | None = None
    visual_score: float | None = None
    final_score: float | None = None
    scoring_weights: dict[str, float] = field(default_factory=dict)
    slides: list[SlideFormatResult] = field(default_factory=list)
    summary: str = ""
    critical_issues: list[str] = field(default_factory=list)
    rulebook_version: str = ""
    vision_model: str = ""
    errors: list[str] = field(default_factory=list)
    deck_data: dict[str, Any] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Internal/developer report (full metrics and rule IDs)."""
        return {
            "source_file": self.source_file,
            "mode": self.mode,
            "deck_pass": self.deck_pass,
            "deck_score": self.deck_score,
            "deterministic_score": self.deterministic_score,
            "visual_score": self.visual_score,
            "final_score": self.final_score,
            "scoring_weights": self.scoring_weights,
            "slides": [s.to_dict() for s in self.slides],
            "summary": self.summary,
            "critical_issues": self.critical_issues,
            "rulebook_version": self.rulebook_version,
            "vision_model": self.vision_model,
            "errors": self.errors,
        }


def _service_base_title(title: str) -> str:
    base = re.sub(r"^Delivery status\s*[–-]\s*", "", title, flags=re.I)
    return re.sub(r"\s*\(Contd.*\)\s*$", "", base, flags=re.I).strip()


def _load_content_titles(content_json: Path | None) -> set[str] | None:
    if content_json is None or not content_json.is_file():
        return None
    with open(content_json, encoding="utf-8") as f:
        data = json.load(f)
    slides = data.get("slides", data)
    return {s["title"].strip() for s in slides if s.get("title")}


def _deterministic_slide_pass(
    violations: list[dict[str, Any]],
    *,
    fail_severities: frozenset[str] = _FAIL_SEVERITIES,
) -> bool:
    return not any(v.get("severity") in fail_severities for v in violations)


def _group_violations_by_slide(
    violations: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for v in violations:
        idx = v.get("slide_index")
        if idx is None:
            continue
        grouped.setdefault(int(idx), []).append(v)
    return grouped


def _merge_slide_results(
    deck_data: dict[str, Any],
    *,
    det_by_slide: dict[int, list[dict[str, Any]]],
    visual_by_slide: dict[int, dict[str, Any]],
    ai_by_slide: dict[int, dict[str, Any]],
    use_deterministic: bool,
    use_visual: bool,
    use_ai: bool,
) -> list[SlideFormatResult]:
    results: list[SlideFormatResult] = []
    for slide in deck_data.get("slides", []):
        idx = int(slide["slide_index"])
        title = slide.get("title", "")

        det_violations = list(det_by_slide.get(idx, []))
        vis_slide = visual_by_slide.get(idx, {})
        ai_slide = ai_by_slide.get(idx, {})

        det_scoring = compute_slide_deterministic_score(det_violations)
        det_pass = det_scoring["deterministic_pass"] if use_deterministic else None
        det_score = det_scoring["deterministic_score"] if use_deterministic else None

        vis_scoring = vis_slide.get("scoring") or {}
        vis_pass = vis_slide.get("pass")
        if vis_pass is None:
            vis_pass = vis_scoring.get("visual_pass") if use_visual else None
        vis_score = vis_scoring.get("visual_score") if use_visual else None
        vis_categories = dict(vis_scoring.get("category_scores") or {})
        visual_issues = list(vis_slide.get("issues") or [])
        suggestions = list(vis_slide.get("suggestions") or [])
        strengths = list(vis_slide.get("strengths") or [])

        violations: list[dict[str, Any]] = [
            {**v, "source": "deterministic"} for v in det_violations
        ]
        if use_ai:
            for v in ai_slide.get("violations", []):
                violations.append({**v, "source": "ai_rulebook_legacy"})

        final_score = combine_hybrid_score(
            det_score if use_deterministic else None,
            vis_score if use_visual else None,
            deterministic_weight=_HYBRID_DET_WEIGHT,
            visual_weight=_HYBRID_VIS_WEIGHT,
        )
        if final_score is None and use_deterministic:
            final_score = det_score
        elif final_score is None and use_visual:
            final_score = vis_score

        ai_pass = ai_slide.get("pass") if use_ai else None

        checks: list[bool] = []
        if use_deterministic and det_pass is not None:
            checks.append(det_pass)
        if use_visual and vis_pass is not None:
            checks.append(vis_pass)
        if use_ai and ai_pass is not None:
            checks.append(ai_pass)

        passed = bool(checks) and all(checks)

        results.append(
            SlideFormatResult(
                slide_index=idx,
                title=title,
                passed=passed,
                deterministic_pass=det_pass,
                visual_pass=vis_pass,
                ai_pass=ai_pass,
                deterministic_score=det_score,
                visual_score=vis_score,
                final_score=final_score,
                score=final_score,
                category_scores=vis_categories,
                violations=violations,
                visual_issues=visual_issues,
                suggestions=suggestions,
                strengths=strengths,
                has_critical_violation=bool(det_scoring.get("has_critical_violation")),
            )
        )
    return results


def _run_visual_review(
    ppt_path: Path,
    deck_data: dict[str, Any],
    det_by_slide: dict[int, list[dict[str, Any]]],
    *,
    slide_indices: list[int] | None = None,
    images_dir: Path | None = None,
    quiet_vision_log: bool = False,
    show_progress: bool = False,
) -> tuple[dict[int, dict[str, Any]], str]:
    """Render delivery slides and run subjective visual quality review."""
    configure_vision_logging(
        log_path=default_log_path(near=ppt_path),
        console=not quiet_vision_log,
    )
    indices = slide_indices
    if indices is None:
        indices = [s["slide_index"] for s in list_delivery_slide_indices(ppt_path)]

    out_dir = images_dir
    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp(prefix="ppt_format_eval_", dir=ppt_path.parent))

    exported = export_slides_to_png(ppt_path, out_dir, slide_indices=indices)
    rendered = [
        RenderedSlide(
            slide_index=item["slide_index"],
            title=item.get("title", ""),
            image_path=Path(item["image_path"]),
        )
        for item in exported
    ]
    batch = RenderBatch(ppt_path=ppt_path, output_dir=out_dir, slides=rendered)
    slide_contexts = build_vision_context_by_slide(
        deck_data, violations_by_slide=det_by_slide
    )
    build_service_chain_by_slide(compute_service_chains(deck_data["slides"]))
    cross_slide_suggestions = supplement_continuation_suggestions(
        deck_data.get("slides", [])
    )
    contd_waste_issues = supplement_contd_hl_waste_issues(deck_data.get("slides", []))

    def _progress(slide: RenderedSlide, n: int, total: int) -> None:
        if show_progress:
            print(
                f"Visual review: slide {slide.slide_index} ({n}/{total})…",
                flush=True,
            )

    report = QualitativeVisionReviewer().evaluate(
        batch,
        slide_contexts=slide_contexts,
        on_slide_start=_progress if show_progress else None,
    )

    by_slide: dict[int, dict[str, Any]] = {}
    for slide in report.slides:
        idx = slide.slide_number
        if idx is None:
            continue
        ctx = slide_contexts.get(int(idx), {})
        raw_issues = [i.to_dict() for i in slide.issues]
        kept, suppressed = filter_vision_issues(raw_issues, ctx)

        # Premature continuation → suggestions only (not scoring failures).
        suggestions = list(cross_slide_suggestions.get(int(idx), []))
        for issue in kept:
            if issue.get("category") == "premature_hl_continuation":
                suggestions.append({
                    "type": "content_organization",
                    "priority": "low",
                    "slide_index": idx,
                    "message": (
                        "This continuation slide contains very little Highlights content. "
                        "Consider merging it with the previous slide if appropriate."
                    ),
                    "detail": issue.get("description", ""),
                    "source": issue.get("source", "vision"),
                })
        kept = [
            i for i in kept
            if i.get("category") != "premature_hl_continuation"
        ]

        det_violations = det_by_slide.get(int(idx), [])
        layout_owns_hl_container = layout_owns_hl_container_finding(det_violations)
        if not layout_owns_hl_container:
            for supplement in contd_waste_issues.get(int(idx), []):
                if not any(
                    existing.get("category") == supplement.get("category")
                    for existing in kept
                ):
                    kept.append(supplement)

        scoring = compute_visual_score_result(
            slide,
            visual_score=slide.visual_score,
            category_scores=slide.category_scores or None,
        )
        visual_pass, adjusted_score = resolve_visual_pass_after_gating(
            visual_score=scoring.get("visual_score"),
            kept_issues=kept,
            suppressed_issues=suppressed,
            slide_ctx=ctx,
        )
        scoring = {**scoring, "visual_score": adjusted_score, "visual_pass": visual_pass}
        by_slide[int(idx)] = {
            "pass": visual_pass,
            "scoring": scoring,
            "issues": kept,
            "suggestions": suggestions,
            "strengths": list(slide.strengths),
            "layout_context": ctx,
            "suppressed_issues": suppressed,
        }
    return by_slide, report.vision_model


def evaluate_ppt_format(
    ppt_path: str | Path,
    *,
    mode: EvaluatorMode = "full",
    content_json: Path | None = None,
    scope_all_slides: bool = False,
    images_dir: Path | None = None,
    rulebook_path: Path | None = None,
    include_visual: bool | None = None,
    include_vision: bool | None = None,
    quiet_vision_log: bool = False,
) -> DeckFormatReport:
    """
    Hybrid evaluation: deterministic geometry (source of truth) + visual AI review.

    Modes:
    - ``full`` (default): deterministic validation + visual quality review (rendered PNG).
    - ``deterministic``: measurable layout rules only (no API).
    - ``visual``: subjective visual review only (rendered PNG + vision API).
    - ``ai``: **deprecated** legacy rulebook LLM auditor (typography/structure metrics).

    Pass ``include_visual=False`` to skip visual review in full mode (deterministic only).

    Per-slide pass requires every enabled layer to pass.
    Critical deterministic violations (overlap, clipping, footer intrusion) auto-fail
    the slide regardless of visual score.
    """
    ppt_path = Path(ppt_path).resolve()
    rulebook = load_rulebook(rulebook_path)

    # Backward compat: include_vision alias for include_visual
    if include_visual is None:
        include_visual = include_vision if include_vision is not None else True

    use_deterministic = mode in ("full", "deterministic")
    use_visual = mode == "visual" or (mode == "full" and include_visual)
    use_ai = mode == "ai"

    deck_data = extract_deck(ppt_path)
    content_titles = _load_content_titles(content_json)
    errors: list[str] = []

    det_by_slide: dict[int, list[dict[str, Any]]] = {}
    if use_deterministic:
        det = detect_deck_violations(
            deck_data,
            content_titles=content_titles,
            scope_all_slides=scope_all_slides,
        )
        det_by_slide = _group_violations_by_slide(det.get("violations", []))

    visual_by_slide: dict[int, dict[str, Any]] = {}
    vision_model = ""
    if use_visual:
        try:
            scope_indices = None
            if content_titles and not scope_all_slides:
                allowed = {t.strip().lower() for t in content_titles}
                scope_indices = [
                    s["slide_index"]
                    for s in list_delivery_slide_indices(ppt_path)
                    if _service_base_title(s.get("title", "")).lower() in allowed
                ]
            visual_by_slide, vision_model = _run_visual_review(
                ppt_path,
                deck_data,
                det_by_slide,
                slide_indices=scope_indices,
                images_dir=images_dir,
                quiet_vision_log=quiet_vision_log,
                show_progress=quiet_vision_log,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Visual evaluation failed: {exc}")
            if mode == "visual":
                raise

    ai_by_slide: dict[int, dict[str, Any]] = {}
    ai_result: dict[str, Any] = {}
    if use_ai:
        errors.append(
            "Mode 'ai' is deprecated — use 'full' for hybrid deterministic + visual review."
        )
        if not llm_configured():
            errors.append(
                "LLM not configured — skipped legacy AI rulebook evaluation."
            )
            raise RuntimeError(errors[-1])
        try:
            ai_result = evaluate_deck_format(ppt_path, rulebook_path)
            for slide in ai_result.get("slides", []):
                ai_by_slide[int(slide["slide_index"])] = slide
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Legacy AI evaluation failed: {exc}")
            raise

    slides = _merge_slide_results(
        deck_data,
        det_by_slide=det_by_slide,
        visual_by_slide=visual_by_slide,
        ai_by_slide=ai_by_slide,
        use_deterministic=use_deterministic,
        use_visual=use_visual and bool(visual_by_slide),
        use_ai=use_ai and bool(ai_by_slide),
    )

    if content_titles and not scope_all_slides:
        allowed_lower = {t.strip().lower() for t in content_titles}
        slides = [
            s
            for s in slides
            if _service_base_title(s.title).lower() in allowed_lower
        ]

    deck_pass = bool(slides) and all(s.passed for s in slides)

    det_deck_score = compute_deck_deterministic_score(
        [{"deterministic_score": s.deterministic_score} for s in slides]
    )
    vis_deck_score = compute_deck_visual_score(
        [{"visual_score": s.visual_score} for s in slides]
    )
    final_deck_score = combine_hybrid_score(
        det_deck_score,
        vis_deck_score,
        deterministic_weight=_HYBRID_DET_WEIGHT,
        visual_weight=_HYBRID_VIS_WEIGHT,
    )

    summary_parts = []
    if use_deterministic:
        n_fail = sum(1 for s in slides if s.deterministic_pass is False)
        score_txt = f", avg {det_deck_score}" if det_deck_score is not None else ""
        summary_parts.append(
            f"Deterministic: {len(slides) - n_fail}/{len(slides)} pass{score_txt}"
        )
    if use_visual and visual_by_slide:
        n_fail = sum(1 for s in slides if s.visual_pass is False)
        score_txt = f", avg {vis_deck_score}" if vis_deck_score is not None else ""
        summary_parts.append(
            f"Visual: {len(slides) - n_fail}/{len(slides)} pass{score_txt}"
        )
    if use_ai and ai_by_slide:
        n_fail = sum(1 for s in slides if s.ai_pass is False)
        summary_parts.append(f"Legacy AI rulebook: {len(slides) - n_fail}/{len(slides)} pass")

    critical_issues = [
        f"Slide {s.slide_index}: {v.get('rule_id')} — {v.get('message')}"
        for s in slides
        for v in s.violations
        if v.get("severity") == "critical"
    ]

    return DeckFormatReport(
        source_file=str(ppt_path),
        mode=mode,
        deck_pass=deck_pass,
        deck_score=final_deck_score,
        deterministic_score=det_deck_score,
        visual_score=vis_deck_score,
        final_score=final_deck_score,
        scoring_weights={
            "deterministic": _HYBRID_DET_WEIGHT,
            "visual": _HYBRID_VIS_WEIGHT,
        },
        slides=slides,
        summary="; ".join(summary_parts) or "No slides evaluated.",
        critical_issues=critical_issues or list(ai_result.get("critical_issues") or []),
        rulebook_version=rulebook.get("meta", {}).get("version", ""),
        vision_model=vision_model,
        errors=errors,
        deck_data=deck_data,
    )


def format_deck_pass_fail_report(report: DeckFormatReport) -> str:
    """Human-readable PASS/FAIL report for terminal output."""
    lines = [
        f"Deck: {report.source_file}",
        f"Evaluator: {report.mode} (rulebook v{report.rulebook_version or '?'})",
    ]
    if report.deterministic_score is not None:
        lines.append(f"Deterministic score: {report.deterministic_score}/100")
    if report.visual_score is not None:
        lines.append(f"Visual score: {report.visual_score}/100")
    if report.final_score is not None:
        weights = report.scoring_weights
        w_det = weights.get("deterministic", _HYBRID_DET_WEIGHT)
        w_vis = weights.get("visual", _HYBRID_VIS_WEIGHT)
        lines.append(
            f"Final score: {report.final_score}/100 "
            f"({w_det:.0%} deterministic + {w_vis:.0%} visual)"
        )
    lines.append(f"Result: {'PASS' if report.deck_pass else 'FAIL'}")
    if report.summary:
        lines.append(report.summary)
    if report.vision_model:
        lines.append(f"Vision model: {report.vision_model}")
    if report.errors:
        lines.append("")
        lines.append("Warnings:")
        for err in report.errors:
            lines.append(f"  - {err}")
    if report.critical_issues:
        lines.append("")
        lines.append("Critical issues:")
        for issue in report.critical_issues:
            lines.append(f"  - {issue}")
    lines.append("")
    lines.append("Per slide:")
    for slide in report.slides:
        status = "PASS" if slide.passed else "FAIL"
        parts = [status]
        if slide.deterministic_pass is not None:
            parts.append(f"det={'PASS' if slide.deterministic_pass else 'FAIL'}")
            if slide.deterministic_score is not None:
                parts.append(f"det_score={slide.deterministic_score}")
        if slide.visual_pass is not None:
            parts.append(f"vis={'PASS' if slide.visual_pass else 'FAIL'}")
            if slide.visual_score is not None:
                parts.append(f"vis_score={slide.visual_score}")
        if slide.final_score is not None:
            parts.append(f"final={slide.final_score}")
        lines.append(
            f"  Slide {slide.slide_index:2d}  {' | '.join(parts)}  {slide.title[:50]}"
        )
        for v in slide.violations[:5]:
            sev = v.get("severity", "?").upper()
            rid = v.get("rule_id", "?")
            msg = v.get("message", "")[:90]
            src = v.get("source", "rule")
            lines.append(f"           [{sev}] {rid} ({src}): {msg}")
        for issue in slide.visual_issues[:3]:
            cat = issue.get("category", "?")
            msg = issue.get("description", "")[:90]
            lines.append(f"           [VISUAL] {cat}: {msg}")
        if len(slide.violations) > 5:
            lines.append(f"           … +{len(slide.violations) - 5} more violations")
    lines.append("")
    lines.append(f"Overall: {'PASS' if report.deck_pass else 'FAIL'}")
    return "\n".join(lines)


def save_evaluation_reports(
    report: DeckFormatReport,
    *,
    json_path: Path,
    report_path: Path,
    internal_json_path: Path | None = None,
    ai_json_path: Path | None = None,
    ai_report_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write user-facing JSON + text reports; optional internal and AI visual reports."""
    from app.services.ppt_format_user_report import (
        build_ai_visual_evaluation_report,
        build_user_evaluation_report,
        format_ai_visual_evaluation_text,
        format_user_evaluation_text,
    )

    json_path = Path(json_path)
    report_path = Path(report_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    deck_data = report.deck_data or {"slides": []}
    user_report = build_user_evaluation_report(report, deck_data)
    terminal_text = format_user_evaluation_text(user_report)

    json_path.write_text(
        json.dumps(user_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report_path.write_text(terminal_text, encoding="utf-8")

    if internal_json_path is not None:
        internal_json_path = Path(internal_json_path)
        internal_json_path.parent.mkdir(parents=True, exist_ok=True)
        internal_payload = {
            **report.to_dict(),
            "_internal": {
                "deck_slides": deck_data.get("slides", []),
                "note": "Developer/debug metrics — not shown to business users.",
            },
        }
        internal_json_path.write_text(
            json.dumps(internal_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    has_visual = report.vision_model or any(
        s.visual_score is not None or s.visual_issues for s in report.slides
    )
    if has_visual and (ai_json_path is not None or ai_report_path is not None):
        ai_report = build_ai_visual_evaluation_report(report)
        if ai_json_path is not None:
            ai_json_path = Path(ai_json_path)
            ai_json_path.parent.mkdir(parents=True, exist_ok=True)
            ai_json_path.write_text(
                json.dumps(ai_report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        if ai_report_path is not None:
            ai_report_path = Path(ai_report_path)
            ai_report_path.parent.mkdir(parents=True, exist_ok=True)
            ai_report_path.write_text(
                format_ai_visual_evaluation_text(ai_report),
                encoding="utf-8",
            )

    return json_path, report_path
