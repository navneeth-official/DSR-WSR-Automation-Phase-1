"""Tests for validation finding deduplication."""

from __future__ import annotations

from app.validation.dedupe import dedupe_findings


def test_hl_util_dropped_when_bottom_waste_present() -> None:
    findings = [
        {"slide_number": 8, "rule_id": "HL-BOTTOM-WASTE-01", "severity": "warn"},
        {"slide_number": 8, "rule_id": "HL-UTIL-01", "severity": "warn"},
    ]
    deduped = dedupe_findings(findings)
    rule_ids = {f["rule_id"] for f in deduped}
    assert rule_ids == {"HL-BOTTOM-WASTE-01"}


def test_cont_hl_suppresses_bottom_waste_on_same_slide() -> None:
    findings = [
        {"slide_number": 9, "rule_id": "CONT-HL-01", "severity": "fail"},
        {"slide_number": 9, "rule_id": "HL-BOTTOM-WASTE-01", "severity": "warn"},
        {"slide_number": 9, "rule_id": "HL-UTIL-01", "severity": "warn"},
    ]
    deduped = dedupe_findings(findings)
    rule_ids = {f["rule_id"] for f in deduped}
    assert rule_ids == {"CONT-HL-01"}
