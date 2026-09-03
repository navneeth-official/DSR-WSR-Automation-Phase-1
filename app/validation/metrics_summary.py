"""Per-slide validation summaries for validation_report.md/json."""

from __future__ import annotations

from typing import Any

from app.services.hl_waste_limits import (
    container_waste_report_limit,
    hl_bottom_waste_in,
    hl_waste_limit,
)
from app.services.ppt_hl_typography import detect_hl_typography_violations
from app.services.template_calibration import TemplateLayoutThresholds
from app.services.template_typography import TemplateTypographySpec
from app.validation.severity import normalize_severity
from app.validation.typography_display import dedupe_paragraph_rows, enrich_paragraph_row

_CHECK_CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("typography", "Typography (font, size, color, bold, spacing)", ("HL-P-", "HL-HDR-", "HL-SPC-")),
    ("bullets", "Bullets (category headers)", ("HL-P-04", "HL-HDR-01", "HL-HDR-02", "HL-HDR-03")),
    (
        "container_space",
        "Container space (HL/KA top & bottom waste)",
        ("HL-TOP-WASTE", "HL-BOTTOM-WASTE", "HL-UTIL", "KA-TOP-WASTE", "KA-BOTTOM-WASTE", "KA-UTIL"),
    ),
    (
        "layout",
        "Layout (HL/KA placement, overlap, stretch)",
        ("LAY-", "KA-PLC", "KA-OVERLAP", "HL-OVERFLOW", "HL-SIZE", "CONT-", "KA-SIZE", "HL-WASTE"),
    ),
    ("footer", "Footer clearance", ("GEO-",)),
    ("title", "Slide title", ("TITLE-",)),
)


def _category_for_rule(rule_id: str) -> str:
    for key, _, prefixes in _CHECK_CATEGORIES:
        if any(rule_id.startswith(prefix) for prefix in prefixes):
            return key
    return "other"


def _status_from_findings(findings: list[dict[str, Any]]) -> str:
    for finding in findings:
        if normalize_severity(finding) == "fail":
            return "fail"
    if findings:
        return "warn"
    return "pass"


def _typography_audit(
    hl: dict[str, Any],
    *,
    slide_index: int | None,
    title: str,
    typography: TemplateTypographySpec | None,
) -> list[dict[str, Any]]:
    if typography is None:
        return []
    return detect_hl_typography_violations(
        hl,
        slide_index=slide_index,
        title=title,
        typography=typography,
    )


def _paragraph_audit(hl: dict[str, Any], typography: TemplateTypographySpec | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if typography is None:
        return rows
    for paragraph_index, para in enumerate(hl.get("paragraphs") or []):
        role = str(para.get("role") or "")
        text = (para.get("text") or "").strip()
        if not text or role == "blank":
            continue
        spec = typography.role_spec(role)
        if spec is None:
            continue
        runs = para.get("runs") or []
        primary = next((r for r in runs if (r.get("text") or "").strip()), runs[0] if runs else {})
        rows.append(
            {
                "paragraph_index": paragraph_index,
                "role": role,
                "text_preview": text[:72] + ("…" if len(text) > 72 else ""),
                "font": primary.get("font"),
                "size_pt": primary.get("size_pt"),
                "bold": primary.get("bold"),
                "color": primary.get("color"),
                "expected_fonts": sorted(spec.allowed_fonts),
                "expected_size_pt": spec.size_pt,
                "expected_bold": spec.bold,
                "expected_colors": sorted(spec.allowed_colors),
                "line_spacing_pt": para.get("line_spacing_pt"),
                "expected_line_spacing_pt": spec.line_spacing_pt,
                "expected_max_spc_bef_pt": spec.max_spc_bef_pt,
            }
        )
    return rows


def build_slide_check_summaries(
    report_slides: list[Any],
    deck_data: dict[str, Any] | None,
    *,
    typography: TemplateTypographySpec | None = None,
    thresholds: TemplateLayoutThresholds | None = None,
) -> list[dict[str, Any]]:
    """Build per-slide validation matrix covering all deterministic check categories."""
    deck_by_index = {
        int(s["slide_index"]): s for s in (deck_data or {}).get("slides", [])
    }
    summaries: list[dict[str, Any]] = []

    for slide_result in report_slides:
        slide_index = int(slide_result.slide_index)
        slide_data = deck_by_index.get(slide_index, {})
        det_violations = [
            v for v in slide_result.violations if v.get("source") == "deterministic"
        ]

        by_category: dict[str, list[dict[str, Any]]] = {key: [] for key, _, _ in _CHECK_CATEGORIES}
        by_category["other"] = []
        for violation in det_violations:
            by_category[_category_for_rule(str(violation.get("rule_id") or ""))].append(violation)

        hl = slide_data.get("highlights") or {}
        typo_violations = _typography_audit(
            hl,
            slide_index=slide_index,
            title=slide_result.title,
            typography=typography,
        ) if hl else []

        if typo_violations and not by_category["typography"]:
            by_category["typography"] = typo_violations

        bottom_waste = hl_bottom_waste_in(slide_data) if hl else None
        checks: dict[str, Any] = {}
        for key, label, _ in _CHECK_CATEGORIES:
            cat_findings = by_category.get(key) or []
            entry: dict[str, Any] = {
                "label": label,
                "status": _status_from_findings(cat_findings),
                "finding_count": len(cat_findings),
                "rule_ids": sorted({str(v.get("rule_id") or "") for v in cat_findings if v.get("rule_id")}),
            }
            if key == "typography" and hl:
                audited = dedupe_paragraph_rows(_paragraph_audit(hl, typography))
                entry["paragraphs_audited"] = [
                    enrich_paragraph_row(row, typo_violations) for row in audited
                ]
                entry["finding_count"] = max(entry["finding_count"], len(typo_violations))
                if typo_violations and entry["status"] == "pass":
                    entry["status"] = _status_from_findings(
                        [{"severity": "fail" if v.get("severity") in {"critical", "major"} else "warn"} for v in typo_violations]
                    )
            if key == "container_space" and hl and thresholds is not None:
                entry["metrics"] = {
                    "hl_bottom_waste_in": bottom_waste,
                    "hl_bottom_waste_limit_in": container_waste_report_limit(
                        hl_waste_limit(slide_data, thresholds)
                    ),
                    "hl_top_waste_in": slide_data.get("hl_waste_above_text_in"),
                    "hl_top_waste_limit_in": thresholds.hl_waste_above_text_max_in,
                }
            checks[key] = entry

        summaries.append(
            {
                "slide_index": slide_index,
                "slide_number": slide_index,
                "title": slide_result.title,
                "service": slide_result.title,
                "deterministic_pass": slide_result.deterministic_pass,
                "deterministic_score": slide_result.deterministic_score,
                "checks": checks,
            }
        )

    return summaries


def category_labels() -> list[tuple[str, str]]:
    return [(key, label) for key, label, _ in _CHECK_CATEGORIES]
