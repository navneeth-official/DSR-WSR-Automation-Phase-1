"""Generate sample validation_report JSON + Markdown for review (deterministic only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_violations import detect_deck_violations


def _deck_pass(findings: list[dict]) -> bool:
    return not any(f.get("severity") == "critical" for f in findings)


def _example_findings() -> list[dict]:
    """Illustrative rows showing the v1 report shape (not from this deck run)."""
    return [
        {
            "slide_index": 15,
            "slide_number": 16,
            "slide_title": "Delivery Status - Global Sourcing Solution",
            "area": "key_activities",
            "rule_id": "CONTENT-KA-01",
            "severity": "critical",
            "message": "KA content cell contains leftover template text; expected empty placeholders.",
            "metrics": {"sample_text": "Create tobacco-rebates endpoint"},
            "_note": "example only",
        },
        {
            "slide_index": 15,
            "slide_number": 16,
            "slide_title": "Delivery Status - Global Sourcing Solution",
            "area": "highlights",
            "rule_id": "HL-SPC-01",
            "severity": "major",
            "message": "Highlights content has excessive unused space above text (top gap).",
            "metrics": {"hl_waste_below_text_in": 0.52, "limit": 0.15},
            "_note": "example only",
        },
        {
            "slide_index": 16,
            "slide_number": 17,
            "slide_title": "Delivery Status - Global Sourcing Solution (Contd..)",
            "area": "layout",
            "rule_id": "KA-OVERLAP-01",
            "severity": "critical",
            "message": "Key Activities table overlaps footer safe zone.",
            "metrics": {"ka_bottom_in": 6.82, "footer_limit_in": 6.75},
            "_note": "example only",
        },
        {
            "slide_index": 2,
            "slide_number": 3,
            "slide_title": "Delivery Status - Cost Core Service",
            "area": "highlights.typography",
            "rule_id": "HL-HDR-01",
            "severity": "major",
            "message": "Category header bullet is not G10X Wingdings arrow (lvl 7).",
            "metrics": {"expected": "Wingdings Ø lvl 7", "actual": "round bullet lvl 1"},
            "_note": "example only",
        },
        {
            "slide_index": 15,
            "slide_number": 16,
            "slide_title": "Delivery Status - Global Sourcing Solution",
            "area": "content",
            "rule_id": "CONTENT-HL-02",
            "severity": "critical",
            "message": "Story from ppt_content.json not found on slide: 'Add pagination support to supplier lookup API endpoint'.",
            "metrics": {"project": "Global Sourcing Solution", "bucket": "inprogress"},
            "_note": "example only",
        },
    ]


def main() -> int:
    ppt = ROOT / "output" / "HEB_Delivery_Status_Haskell_July2025.pptx"
    content = ROOT / "output" / "ppt_content.json"
    template = ROOT / "templates" / "G10X H-E-B WSR Haskell Location Pharmacy GSS PAM 11 July 2025.pptx"

    deck_data = extract_deck(ppt)
    det = detect_deck_violations(deck_data, scope_all_slides=True)
    deck_pass = _deck_pass(det.get("violations", []))

    findings = []
    for v in det.get("violations", []):
        metrics = {
            k: v[k]
            for k in (
                "actual",
                "limit",
                "hl_waste_below_text_in",
                "value",
                "expected",
                "ka_bottom_in",
                "footer_limit_in",
            )
            if k in v
        }
        findings.append(
            {
                "slide_index": v.get("slide_index"),
                "slide_number": (v.get("slide_index") or 0) + 1,
                "slide_title": v.get("slide_title", ""),
                "area": v.get("target") or v.get("category") or "layout",
                "rule_id": v.get("rule_id", ""),
                "severity": v.get("severity", "minor"),
                "message": v.get("message") or v.get("description") or "",
                "metrics": metrics,
            }
        )

    by_sev = {"critical": 0, "major": 0, "minor": 0}
    for f in findings:
        sev = f["severity"]
        by_sev[sev] = by_sev.get(sev, 0) + 1

    sample = {
        "report_version": "v1-sample",
        "source_file": str(ppt),
        "template_file": str(template),
        "content_file": str(content),
        "deck_pass": deck_pass,
        "summary": {
            "total_findings": len(findings),
            "critical": by_sev.get("critical", 0),
            "major": by_sev.get("major", 0),
            "minor": by_sev.get("minor", 0),
            "checks_run": [
                "layout_geometry",
                "typography_bullets",
                "hl_waste_thresholds",
                "content_scope",
            ],
        },
        "executive_summary": (
            "FAIL — critical layout or overlap issues detected."
            if not deck_pass
            else f"PASS — {len(findings)} non-critical findings only."
        ),
        "findings": findings,
        "example_findings_if_empty": _example_findings() if not findings else [],
    }

    out_json = ROOT / "output" / "validation_report_sample.json"
    out_json.write_text(json.dumps(sample, indent=2), encoding="utf-8")

    md_lines = [
        "# Validation Report (Sample)",
        "",
        f"**Deck:** `{ppt.name}`  ",
        f"**Template:** `{template.name}`  ",
        f"**Content:** `{content.name}`  ",
        f"**Result:** {'PASS' if deck_pass else 'FAIL'}",
        "",
        "## Summary",
        "",
        f"- Total findings: **{len(findings)}**",
        f"- Critical: **{by_sev.get('critical', 0)}** | "
        f"Major: **{by_sev.get('major', 0)}** | "
        f"Minor: **{by_sev.get('minor', 0)}**",
        "",
        sample["executive_summary"],
        "",
    ]
    examples = sample.get("example_findings_if_empty") or []
    if examples:
        md_lines.extend(
            [
                "> **Note:** This deck had **0 real violations** with current rules.",
                "> The examples below show the **target report shape** for v1.",
                "",
                "## Example findings (illustrative)",
                "",
            ]
        )
        for f in examples:
            md_lines.append(f"### Slide {f['slide_number']} — {f['slide_title'][:55]}")
            md_lines.append(f"- **Rule:** `{f['rule_id']}` ({f['severity']})")
            md_lines.append(f"- **Area:** {f['area']}")
            md_lines.append(f"- **Issue:** {f['message']}")
            if f.get("metrics"):
                md_lines.append(f"- **Metrics:** `{json.dumps(f['metrics'])}`")
            md_lines.append("")

    md_lines.extend(
        [
            "## Real findings from this run",
            "",
        ]
    )
    if not findings:
        md_lines.append("_None — deck passed current deterministic rules._")
        md_lines.append("")
    else:
        md_lines.append("")
    if findings:
        for f in findings[:15]:
            md_lines.append(f"### Slide {f['slide_number']} — {f['slide_title'][:55]}")
            md_lines.append(f"- **Rule:** `{f['rule_id']}` ({f['severity']})")
            md_lines.append(f"- **Area:** {f['area']}")
            md_lines.append(f"- **Issue:** {f['message'][:220]}")
            if f.get("metrics"):
                md_lines.append(f"- **Metrics:** `{json.dumps(f['metrics'])}`")
            md_lines.append("")

    out_md = ROOT / "output" / "validation_report_sample.md"
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"deck_pass={deck_pass}")
    print(f"findings={len(findings)} critical={by_sev.get('critical', 0)}")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0 if deck_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
