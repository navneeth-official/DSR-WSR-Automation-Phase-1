"""Remove redundant validation findings so each slide shows one clear message per problem."""

from __future__ import annotations

from typing import Any

# winning rule -> rules it makes redundant *on the same slide*.
# All of these describe the same underlying problem ("too much empty space in HL")
# and would otherwise produce several near-identical cards and annotated images.
_SUPPRESSES: dict[str, frozenset[str]] = {
    "CONT-HL-01": frozenset({"HL-BOTTOM-WASTE-01", "HL-UTIL-01", "HL-WASTE-01"}),
    "CONT-SPARSE-01": frozenset({"HL-WASTE-01"}),
    "HL-SIZE-01": frozenset({"HL-WASTE-01"}),
    "HL-BOTTOM-WASTE-01": frozenset({"HL-UTIL-01"}),
}


def _slide_key(finding: dict[str, Any]) -> Any:
    for key in ("slide_number", "slide_index"):
        value = finding.get(key)
        if value is not None:
            return (key, value)
    return None


def dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return findings with redundant / duplicate entries removed (order preserved)."""
    rules_by_slide: dict[Any, set[str]] = {}
    for finding in findings:
        rules_by_slide.setdefault(_slide_key(finding), set()).add(
            str(finding.get("rule_id") or "")
        )

    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, str, str]] = set()
    for finding in findings:
        slide_key = _slide_key(finding)
        rule_id = str(finding.get("rule_id") or "")
        present = rules_by_slide.get(slide_key, set())

        suppressed = any(
            winner in present and rule_id in losers
            for winner, losers in _SUPPRESSES.items()
        )
        if suppressed:
            continue

        signature = (slide_key, rule_id, str(finding.get("issue") or finding.get("message") or ""))
        if signature in seen:
            continue
        seen.add(signature)
        result.append(finding)
    return result
