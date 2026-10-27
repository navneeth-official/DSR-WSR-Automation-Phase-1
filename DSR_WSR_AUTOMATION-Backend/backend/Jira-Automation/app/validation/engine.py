"""Orchestrate deck validation and annotated reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pptx import Presentation

from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_violations import (
    compute_service_chains,
    detect_slide_violations,
    terminal_slide_indices_for_chains,
)
from app.services.ppt_layout_metrics import EMU_PER_INCH
from app.services.template_calibration import TemplateLayoutThresholds, load_thresholds
from app.services.template_typography import TemplateTypographySpec, load_template_typography
from app.validation.annotate import annotate_findings
from app.validation.dedupe import dedupe_findings
from app.validation.layout_checks import detect_supplemental_layout_violations
from app.validation.metrics_summary import SlideCheckInput, build_slide_check_summaries
from app.validation.report import build_report_payload, write_json_report, write_markdown_report
from app.validation.severity import deck_passes, normalize_severity
from app.validation.user_messages import enrich_finding

CHECKS_RUN = [
    "layout_geometry",
    "typography_bullets",
    "hl_waste_thresholds",
    "footer_clearance",
    "container_space",
]


@dataclass
class ValidationResult:
    deck_pass: bool
    findings: list[dict[str, Any]]
    report_json: Path
    report_md: Path
    annotation_dir: Path | None = None
    slide_summaries: list[dict[str, Any]] = field(default_factory=list)


def _collect_violations(
    deck_data: dict[str, Any],
    *,
    thresholds: TemplateLayoutThresholds,
    typography: TemplateTypographySpec,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    slides = deck_data.get("slides", [])

    chains = compute_service_chains(slides)
    ka_terminal = terminal_slide_indices_for_chains(chains)

    for slide in slides:
        slide_violations = detect_slide_violations(
            slide,
            thresholds=thresholds,
            typography=typography,
            ka_placement_terminal_indices=ka_terminal,
        )
        existing = {str(v.get("rule_id")) for v in slide_violations}
        slide_violations.extend(
            detect_supplemental_layout_violations(
                slide,
                thresholds=thresholds,
                existing_rule_ids=existing,
            )
        )
        violations.extend(slide_violations)

    return violations


def validate_deck(
    ppt_path: str | Path,
    *,
    template_path: str | Path,
    output_dir: str | Path | None = None,
    annotate: bool = False,
    thresholds: TemplateLayoutThresholds | None = None,
    use_rendered_bounds: bool = True,
    report_json_path: str | Path | None = None,
    report_md_path: str | Path | None = None,
    annotation_dir: str | Path | None = None,
) -> ValidationResult:
    """
    Validate a generated deck.

    By default outputs go to ``<output_dir>/validation_report.json|md`` and
    ``<output_dir>/validation/``. ``report_json_path``, ``report_md_path`` and
    ``annotation_dir`` override those locations (used for per-deck WSR output).
    """
    ppt_path = Path(ppt_path).resolve()
    template_path = Path(template_path).resolve()
    thresholds = thresholds or load_thresholds()
    typography = load_template_typography(template_path)

    deck_data = extract_deck(ppt_path, use_rendered_bounds=use_rendered_bounds)
    raw_violations = _collect_violations(
        deck_data,
        thresholds=thresholds,
        typography=typography,
    )

    findings = [
        enrich_finding(violation, severity=normalize_severity(violation))
        for violation in raw_violations
    ]
    findings = dedupe_findings(findings)
    findings.sort(
        key=lambda f: (
            0 if f.get("severity") == "fail" else 1,
            f.get("slide_number") or 0,
            f.get("rule_id") or "",
        )
    )

    out_dir = Path(output_dir) if output_dir else ppt_path.parent
    annotation_dir = Path(annotation_dir) if annotation_dir else out_dir / "validation"
    report_json_path = Path(report_json_path) if report_json_path else out_dir / "validation_report.json"
    report_md_path = Path(report_md_path) if report_md_path else out_dir / "validation_report.md"
    slides_by_index = {
        int(slide["slide_index"]): slide for slide in deck_data.get("slides", [])
    }

    prs = Presentation(str(ppt_path))
    slide_width_in = round(prs.slide_width / EMU_PER_INCH, 4)
    slide_height_in = round(prs.slide_height / EMU_PER_INCH, 4)

    if annotate:
        try:
            annotate_findings(
                ppt_path,
                findings,
                slides_by_index,
                annotation_dir,
                slide_width_in=slide_width_in,
                slide_height_in=slide_height_in,
                footer_limit_in=thresholds.footer_content_max_bottom_in,
            )
        except Exception as exc:  # noqa: BLE001
            for finding in findings:
                finding.setdefault("annotation_error", str(exc))

    findings_by_slide: dict[int, list[dict[str, Any]]] = {}
    for finding in findings:
        if finding.get("slide_index") is not None:
            findings_by_slide.setdefault(int(finding["slide_index"]), []).append(finding)

    slide_inputs = [
        SlideCheckInput(
            slide_index=int(slide["slide_index"]),
            title=str(slide.get("title") or ""),
            violations=findings_by_slide.get(int(slide["slide_index"]), []),
        )
        for slide in deck_data.get("slides", [])
        if slide.get("slide_index") is not None
    ]
    slide_summaries = build_slide_check_summaries(
        slide_inputs,
        deck_data,
        typography=typography,
        checks_run=CHECKS_RUN,
    )

    payload = build_report_payload(
        source_file=ppt_path,
        content_file=None,
        template_file=template_path,
        deck_pass=deck_passes(findings),
        findings=findings,
        checks_run=CHECKS_RUN,
        slide_summaries=slide_summaries,
    )

    report_json = write_json_report(payload, report_json_path)
    report_md = write_markdown_report(payload, report_md_path)

    return ValidationResult(
        deck_pass=payload["deck_pass"],
        findings=findings,
        report_json=report_json,
        report_md=report_md,
        annotation_dir=annotation_dir if annotate else None,
        slide_summaries=slide_summaries,
    )
