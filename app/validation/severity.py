"""Map internal violation severities to validation pass/fail tiers."""

from __future__ import annotations

from typing import Any, Literal

Severity = Literal["fail", "warn"]

# Typography and spacing drift are hard fails for v1 validation.
_FAIL_RULE_IDS = frozenset({
    "HL-HDR-01",
    "HL-HDR-02",
    "HL-HDR-03",
    "HL-P-01",
    "HL-P-02",
    "HL-P-03",
    "HL-P-04",
    "HL-P-05",
    "HL-P-06",
    "HL-SPC-02",
    "HL-SPC-04",
    "HL-WASTE-01",
    "HL-OVERFLOW-01",
    "KA-OVERLAP-01",
    "GEO-01",
    "GEO-02",
    "GEO-03",
    "CONTENT-HL-01",
    "CONTENT-HL-02",
    "CONTENT-KA-01",
    "CONTENT-KA-02",
    "CONTENT-PRJ-01",
    "CONT-HL-01",
    "CONT-SPARSE-01",
})

_WARN_RULE_IDS = frozenset({
    "TITLE-01",
    "TITLE-02",
    "TITLE-03",
    "HL-SPC-01",
    "HL-SPC-03",
    "HL-SIZE-01",
    "KA-SIZE-01",
    "KA-PLC-02",
    "KA-PLC-03",
    "KA-PLC-04",
})


def normalize_severity(violation: dict[str, Any]) -> Severity:
    """Return user-facing severity: fail blocks release, warn is optional polish."""
    rule_id = str(violation.get("rule_id") or "")
    if rule_id in _FAIL_RULE_IDS:
        return "fail"
    if rule_id in _WARN_RULE_IDS:
        return "warn"

    internal = str(violation.get("severity") or "minor").lower()
    if internal == "critical":
        return "fail"
    if internal == "major":
        # Typography rules often arrive as major from ppt_hl_typography.
        if rule_id.startswith(("HL-HDR", "HL-P", "HL-SPC", "CONTENT-")):
            return "fail"
        if rule_id in {"HL-OVERFLOW-01", "KA-OVERLAP-01", "GEO-02"}:
            return "fail"
        return "warn"
    return "warn"


def deck_passes(findings: list[dict[str, Any]]) -> bool:
    return not any(f.get("severity") == "fail" for f in findings)
