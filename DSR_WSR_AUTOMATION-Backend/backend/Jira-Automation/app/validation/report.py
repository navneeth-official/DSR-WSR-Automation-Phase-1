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
) -> dict[str, Any]:
    counts = _count_by_severity(findings)
    slides_to_fix = sorted(
        {
            int(f["slide_number"])
            for f in findings
            if f.get("severity") == "fail" and f.get("slide_number")
        }
    )
    return {
        "report_version": "v1",
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
        "findings": findings,
    }


def write_json_report(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_markdown_report(payload: dict[str, Any], path: Path) -> Path:
    source = Path(payload.get("source_file") or "deck.pptx")
    summary = payload.get("summary") or {}
    findings = payload.get("findings") or []
    deck_pass = payload.get("deck_pass")

    lines = [
        "# Validation Report",
        "",
        f"**Deck:** `{source.name}`  ",
        f"**Result:** {'PASS' if deck_pass else 'FAIL'}",
        "",
        "## Summary",
        "",
        f"- Must fix: **{summary.get('fail', 0)}**",
        f"- Optional polish: **{summary.get('warn', 0)}**",
    ]
    slides = summary.get("slides_to_fix") or []
    if slides:
        lines.append(f"- Slides to open: **{', '.join(str(s) for s in slides)}**")
    lines.extend(["", payload.get("executive_summary", ""), ""])

    fail_findings = [f for f in findings if f.get("severity") == "fail"]
    warn_findings = [f for f in findings if f.get("severity") == "warn"]

    lines.append("## Issues to fix")
    lines.append("")
    if not fail_findings:
        lines.append("_None — deck passed all required checks._")
        lines.append("")
    else:
        for finding in fail_findings:
            lines.extend(_finding_block(finding, report_path=path))

    lines.append("## Optional polish")
    lines.append("")
    if not warn_findings:
        lines.append("_None._")
        lines.append("")
    else:
        for finding in warn_findings:
            lines.extend(_finding_block(finding, report_path=path))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


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


def _finding_block(finding: dict[str, Any], *, report_path: Path) -> list[str]:
    slide_number = finding.get("slide_number") or "?"
    service = finding.get("service") or finding.get("slide_title") or "Slide"
    lines = [
        "────────────────────────────────────────",
        f"Slide {slide_number} — {service}",
        f"Issue:  {finding.get('issue', '')}",
        f"Where:  {finding.get('where', '')}",
        "Fix:",
    ]
    for step in finding.get("fix_steps") or []:
        lines.append(f"        {step}")
    if finding.get("why"):
        lines.append(f"Why:    {finding['why']}")
    image_link = _image_link_markdown(finding.get("image"), report_path)
    if image_link:
        lines.append(f"Photo:  {image_link}")
    lines.append("")
    return lines
