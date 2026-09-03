"""Write validation_report.json and validation_report.md."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _count_by_severity(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"fail": 0, "warn": 0}
    for finding in findings:
        sev = str(finding.get("severity") or "warn")
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def build_report_payload(
    *,
    source_file: Path,
    content_file: Path | None,
    template_file: Path | None,
    deck_pass: bool,
    findings: list[dict[str, Any]],
    checks_run: list[str],
    slide_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    counts = _count_by_severity(findings)
    slides_to_fix = sorted(
        {
            int(f["slide_number"])
            for f in findings
            if f.get("severity") == "fail" and f.get("slide_number")
        }
    )
    by_category: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        category = str(finding.get("area") or "other")
        by_category.setdefault(category, []).append(finding)

    return {
        "report_version": "v2",
        "source_file": str(source_file),
        "template_file": str(template_file) if template_file else None,
        "content_file": str(content_file) if content_file else None,
        "deck_pass": deck_pass,
        "summary": {
            "total_findings": len(findings),
            "fail": counts.get("fail", 0),
            "warn": counts.get("warn", 0),
            "slides_to_fix": slides_to_fix,
            "checks_run": checks_run,
        },
        "executive_summary": (
            f"PASS — {counts.get('warn', 0)} optional polish item(s) only."
            if deck_pass
            else f"FAIL — {counts.get('fail', 0)} issue(s) must be fixed before sending."
        ),
        "findings_by_category": by_category,
        "slide_summaries": slide_summaries or [],
        "findings": findings,
    }


def write_json_report(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


_CHECK_LABELS: dict[str, str] = {
    "typography_bullets": "Fonts & bullets",
    "font_size_bold_spacing": "Font size, bold, line spacing",
    "container_waste_top_bottom": "Empty space in HL/KA boxes",
    "container_utilization": "Box size vs content",
    "layout_geometry": "HL/KA placement",
    "footer_clearance": "Footer clearance",
    "hl_ka_placement": "HL and KA positioning",
    "visual_ai_review": "Visual AI review",
}


def write_markdown_report(payload: dict[str, Any], path: Path) -> Path:
    source = Path(payload.get("source_file") or "deck.pptx")
    summary = payload.get("summary") or {}
    findings = payload.get("findings") or []
    deck_pass = payload.get("deck_pass")
    slide_summaries = payload.get("slide_summaries") or []

    fail_findings = [f for f in findings if f.get("severity") == "fail"]
    warn_findings = [f for f in findings if f.get("severity") == "warn"]

    lines = [
        "# Validation Report",
        "",
        f"**Deck:** `{source.name}`",
        f"**Result:** {'PASS' if deck_pass else 'FAIL'}",
    ]
    template_file = payload.get("template_file")
    if template_file:
        lines.append(f"**Template:** `{Path(template_file).name}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    if deck_pass and not warn_findings:
        lines.append("No issues found.")
    else:
        if fail_findings:
            fail_slides = sorted({f.get("slide_number") for f in fail_findings if f.get("slide_number")})
            lines.append(
                f"- **Must fix:** {len(fail_findings)} on slide(s) "
                f"{', '.join(str(s) for s in fail_slides)}"
            )
        if warn_findings:
            warn_slides = sorted({f.get("slide_number") for f in warn_findings if f.get("slide_number")})
            lines.append(
                f"- **Optional:** {len(warn_findings)} on slide(s) "
                f"{', '.join(str(s) for s in warn_slides)}"
            )
    lines.append("")

    must_fix_blocks = _issue_sections(
        slide_summaries,
        fail_findings,
        title="Must fix",
        include_typography=True,
        report_path=path,
    )
    if must_fix_blocks:
        lines.extend(["## Must fix", ""] + must_fix_blocks)
    elif not deck_pass:
        lines.extend(["## Must fix", "", "_None listed._", ""])

    optional_blocks = _issue_sections(
        slide_summaries,
        warn_findings,
        title="Optional",
        include_typography=False,
        report_path=path,
    )
    if optional_blocks:
        lines.extend(["## Optional polish", ""] + optional_blocks)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _issue_sections(
    slide_summaries: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    *,
    title: str,
    include_typography: bool = False,
    report_path: Path | None = None,
) -> list[str]:
    if not findings:
        return []
    findings_by_slide: dict[int, list[dict[str, Any]]] = {}
    for finding in findings:
        num = finding.get("slide_number")
        if num is not None:
            findings_by_slide.setdefault(int(num), []).append(finding)

    summary_by_number = {int(s.get("slide_number") or 0): s for s in slide_summaries}
    blocks: list[str] = []

    for slide_number in sorted(findings_by_slide):
        slide = summary_by_number.get(slide_number, {})
        service = slide.get("service") or slide.get("title") or f"Slide {slide_number}"
        typography = (slide.get("checks") or {}).get("typography") or {}
        fix_rows = []
        if include_typography:
            fix_rows = [
                row for row in (typography.get("paragraphs_audited") or [])
                if row.get("status") == "fix"
            ]
        slide_findings = findings_by_slide[slide_number]

        blocks.append(f"### Slide {slide_number} — {service}")
        blocks.append("")

        issue_num = 0
        seen_text: set[str] = set()

        for row in fix_rows:
            preview = str(row.get("text_preview") or "").replace("\t", " ").strip()
            if preview in seen_text:
                continue
            seen_text.add(preview)
            issue_num += 1
            blocks.extend(_issue_entry(
                issue_num,
                problem=_row_problem(row),
                where="Highlights text line",
                text_line=preview,
                fix_hint=str(row.get("fix_hint") or ""),
                image=row.get("image"),
                report_path=report_path,
            ))

        for finding in slide_findings:
            issue = str(finding.get("issue") or "")
            if any(issue and issue in str(r.get("text_preview", "")) for r in fix_rows):
                continue
            if fix_rows and str(finding.get("rule_id", "")).startswith("HL-P"):
                continue
            issue_num += 1
            blocks.extend(_issue_entry(
                issue_num,
                problem=issue,
                where=str(finding.get("where") or "This slide"),
                text_line="",
                fix_steps=list(finding.get("fix_steps") or []),
                image=finding.get("image"),
                report_path=report_path,
            ))

        blocks.append("")
    return blocks


def _issue_entry(
    number: int,
    *,
    problem: str,
    where: str,
    text_line: str = "",
    fix_hint: str = "",
    fix_steps: list[str] | None = None,
    image: str | None = None,
    report_path: Path | None = None,
) -> list[str]:
    lines = [f"#### Issue {number}", ""]
    rows: list[tuple[str, str]] = [("Problem", problem), ("Where", where)]
    if text_line:
        rows.append(("Text line", text_line))
    if fix_steps:
        fix_text = "\n".join(f"{i}. {step}" for i, step in enumerate(fix_steps, start=1))
        rows.append(("How to fix", fix_text))
    elif fix_hint:
        rows.append(("How to fix", fix_hint))
    image_markdown = _image_markdown(image, report_path)
    if image_markdown:
        rows.append(("Photo evidence", image_markdown))
    lines.extend(_field_table(rows))
    lines.append("")
    return lines


def _image_markdown(image_path: str | None, report_path: Path | None) -> str | None:
    if not image_path or not report_path:
        return None
    img = Path(image_path)
    if not img.is_file():
        return None
    try:
        rel = img.resolve().relative_to(report_path.parent.resolve())
    except ValueError:
        rel = Path(img.name)
    href = rel.as_posix()
    return f"![Highlighted issue on slide]({href})"


def _field_table(rows: list[tuple[str, str]]) -> list[str]:
    """Two-column markdown table: Field | Detail."""
    out = [
        "| Field | Detail |",
        "| ----- | ------ |",
    ]
    for field, detail in rows:
        safe_detail = detail.replace("|", "/").replace("\n", "<br>")
        out.append(f"| **{field}** | {safe_detail} |")
    return out


def _row_problem(row: dict[str, Any]) -> str:
    issues = row.get("issues") or []
    if issues:
        return "; ".join(issues)
    return f"Has {row.get('actual_style', '?')} — need {row.get('expected_style', '?')}"


def _status_badge(status: str) -> str:
    return {
        "pass": "PASS",
        "fail": "FAIL",
        "warn": "WARN",
        "skip": "SKIP",
    }.get(status, status.upper())


def _finding_block(
    finding: dict[str, Any],
    *,
    report_path: Path,
    include_metrics: bool = True,
) -> list[str]:
    slide_number = finding.get("slide_number") or "?"
    service = finding.get("service") or finding.get("slide_title") or "Slide"
    lines = [
        "────────────────────────────────────────",
        f"**Slide {slide_number} — {service}**",
        f"- **Issue:** {finding.get('issue', '')}",
        f"- **Where:** {finding.get('where', '')}",
        "- **Steps:**",
    ]
    for step in finding.get("fix_steps") or []:
        lines.append(f"  - {step}")
    if finding.get("why"):
        lines.append(f"- **Why it matters:** {finding['why']}")
    if include_metrics:
        metrics = finding.get("metrics")
        if metrics:
            lines.append(f"- **Technical details:** `{json.dumps(metrics, ensure_ascii=False)}`")
    image_link = _image_link_markdown(finding.get("image"), report_path)
    if image_link:
        lines.append(f"- **Annotated slide:** {image_link}")
    lines.append("")
    return lines


def _check_details_text(check: dict[str, Any]) -> str:
    rule_ids = check.get("rule_ids") or []
    if rule_ids:
        return ", ".join(rule_ids)
    metrics = check.get("metrics") or {}
    if metrics:
        parts = []
        bottom = metrics.get("hl_bottom_waste_in")
        bottom_limit = metrics.get("hl_bottom_waste_limit_in")
        if bottom is not None and bottom_limit is not None:
            parts.append(
                f"Bottom empty space {float(bottom):.2f} in "
                f"(only flagged above {float(bottom_limit):.2f} in)"
            )
        top = metrics.get("hl_top_waste_in")
        if top is not None and float(top) > 0:
            parts.append(f"Top empty space {float(top):.2f} in")
        return "; ".join(parts) if parts else "OK"
    if check.get("finding_count"):
        return f"{check['finding_count']} finding(s)"
    return "OK"


def _image_link_markdown(image_path: str | None, report_path: Path) -> str | None:
    if not image_path:
        return None
    img = Path(image_path)
    if not img.is_file():
        return None
    try:
        rel = img.resolve().relative_to(report_path.parent.resolve())
    except ValueError:
        rel = Path(img.name)
    href = rel.as_posix()
    return f"[View annotated slide]({href})"
