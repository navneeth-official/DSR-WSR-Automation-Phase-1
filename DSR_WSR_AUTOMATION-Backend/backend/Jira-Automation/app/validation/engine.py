"""Orchestrate deck validation and annotated reporting."""

from __future__ import annotations

from dataclasses import dataclass
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
from app.validation.layout_checks import detect_supplemental_layout_violations
from app.validation.report import build_report_payload, write_json_report, write_markdown_report
from app.validation.severity import deck_passes, normalize_severity
from app.validation.user_messages import enrich_finding


@dataclass
class ValidationResult:
    deck_pass: bool
    findings: list[dict[str, Any]]
    report_json: Path
    report_md: Path
    annotation_dir: Path | None = None


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
) -> ValidationResult:
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
    findings.sort(
        key=lambda f: (
            0 if f.get("severity") == "fail" else 1,
            f.get("slide_number") or 0,
            f.get("rule_id") or "",
        )
    )

    out_dir = Path(output_dir) if output_dir else ppt_path.parent
    annotation_dir = out_dir / "validation"
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

    checks_run = [
        "layout_geometry",
        "typography_bullets",
        "hl_waste_thresholds",
        "footer_clearance",
    ]

    payload = build_report_payload(
        source_file=ppt_path,
        content_file=None,
        template_file=template_path,
        deck_pass=deck_passes(findings),
        findings=findings,
        checks_run=checks_run,
    )

    report_json = write_json_report(payload, out_dir / "validation_report.json")
    report_md = write_markdown_report(payload, out_dir / "validation_report.md")

    return ValidationResult(
        deck_pass=payload["deck_pass"],
        findings=findings,
        report_json=report_json,
        report_md=report_md,
        annotation_dir=annotation_dir if annotate else None,
    )
