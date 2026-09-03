"""Collapse redundant validation findings that describe the same slide issue."""

from __future__ import annotations

from typing import Any

# When a higher-priority rule is present on a slide, drop the redundant ones.
_HL_WASTE_SUPPRESS: dict[str, frozenset[str]] = {
    "CONT-HL-01": frozenset({
        "HL-BOTTOM-WASTE-01",
        "HL-UTIL-01",
        "HL-WASTE-01",
        "CONT-SPARSE-01",
        "HL-SIZE-01",
    }),
    "HL-BOTTOM-WASTE-01": frozenset({"HL-UTIL-01", "HL-WASTE-01"}),
    "KA-BOTTOM-WASTE-01": frozenset({"KA-UTIL-01"}),
}


def dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate container-waste findings per slide."""
    by_slide: dict[int, set[str]] = {}
    for finding in findings:
        slide = finding.get("slide_number") or finding.get("slide_index")
        rule_id = str(finding.get("rule_id") or "")
        if slide is None or not rule_id:
            continue
        by_slide.setdefault(int(slide), set()).add(rule_id)

    suppress: set[tuple[int, str]] = set()
    for slide_num, rule_ids in by_slide.items():
        for keeper, dropped in _HL_WASTE_SUPPRESS.items():
            if keeper not in rule_ids:
                continue
            for rule_id in dropped:
                if rule_id in rule_ids:
                    suppress.add((slide_num, rule_id))

    if not suppress:
        return findings

    out: list[dict[str, Any]] = []
    for finding in findings:
        slide = finding.get("slide_number") or finding.get("slide_index")
        rule_id = str(finding.get("rule_id") or "")
        if slide is not None and (int(slide), rule_id) in suppress:
            continue
        out.append(finding)
    return out
