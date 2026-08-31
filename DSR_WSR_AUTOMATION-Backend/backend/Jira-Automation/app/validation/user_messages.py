"""Plain-language issue text and fix steps for validation findings."""

from __future__ import annotations

import re
from typing import Any

_AREA_BY_RULE: dict[str, str] = {
    "HL-WASTE-01": "highlights",
    "HL-SIZE-01": "highlights",
    "CONT-HL-01": "highlights",
    "CONT-SPARSE-01": "highlights",
    "HL-OVERFLOW-01": "highlights",
    "HL-SPC-01": "highlights",
    "HL-SPC-02": "highlights",
    "HL-SPC-03": "highlights",
    "HL-SPC-04": "highlights",
    "HL-HDR-01": "highlights",
    "HL-HDR-02": "highlights",
    "HL-HDR-03": "highlights",
    "HL-P-01": "highlights",
    "HL-P-02": "highlights",
    "HL-P-03": "highlights",
    "HL-P-04": "highlights",
    "HL-P-05": "highlights",
    "HL-P-06": "highlights",
    "KA-OVERLAP-01": "layout",
    "KA-SIZE-01": "key_activities",
    "KA-PLC-02": "layout",
    "KA-PLC-03": "layout",
    "KA-PLC-04": "key_activities",
    "GEO-01": "footer",
    "GEO-02": "footer",
    "GEO-03": "footer",
    "CONTENT-HL-01": "content",
    "CONTENT-HL-02": "content",
    "CONTENT-KA-01": "key_activities",
    "CONTENT-KA-02": "key_activities",
    "CONTENT-PRJ-01": "content",
    "TITLE-01": "title",
}

_ANNOT_LABEL_BY_RULE: dict[str, str] = {
    "HL-WASTE-01": "Empty space here",
    "CONT-HL-01": "Empty space here",
    "CONT-SPARSE-01": "Empty space here",
    "HL-SPC-02": "Wrong line spacing",
    "HL-P-01": "Wrong font size",
    "HL-P-02": "Wrong font size",
    "HL-P-03": "Wrong font size",
    "HL-P-04": "Wrong font size",
    "HL-P-05": "Wrong font size",
    "HL-HDR-01": "Wrong bullet format",
    "HL-HDR-02": "Wrong bullet format",
    "HL-HDR-03": "Wrong bullet format",
    "KA-OVERLAP-01": "Overlapping",
    "HL-OVERFLOW-01": "Overlapping",
    "GEO-02": "Too close to footer",
    "CONTENT-KA-01": "Clear this text",
    "CONTENT-KA-02": "Clear this text",
    "CONTENT-HL-02": "Not from report",
}


def _service_label(title: str) -> str:
    base = re.sub(r"^Delivery status\s*[–-]\s*", "", title, flags=re.I)
    base = re.sub(r"\s*\(Contd.*\)\s*$", "", base, flags=re.I).strip()
    return base or title


def _issue_for_rule(rule_id: str, violation: dict[str, Any]) -> str:
    templates: dict[str, str] = {
        "HL-WASTE-01": "Too much empty space in the Highlights box",
        "CONT-HL-01": "Highlights continuation box is taller than needed",
        "CONT-SPARSE-01": "Highlights box is too tall for the amount of text",
        "HL-OVERFLOW-01": "Highlights text runs outside its gray box",
        "KA-OVERLAP-01": "Highlights text overlaps the Key Activities area",
        "GEO-02": "Content is too close to or crosses the footer area",
        "CONTENT-PRJ-01": "A project from this week's report is missing from the deck",
        "CONTENT-HL-02": "A story from this week's report is missing on the slide",
        "CONTENT-KA-01": "Key Activities still shows old sample or leftover text",
        "CONTENT-KA-02": "Key Activities should be empty but contains text",
        "HL-SPC-02": "Line spacing between bullets does not match the template",
        "HL-P-01": "Highlights header font or size does not match the template",
        "HL-P-02": "Sprint line font or size does not match the template",
        "HL-P-03": "Current-week status font or size does not match the template",
        "HL-P-04": "Category header font or size does not match the template",
        "HL-P-05": "Story line font or size does not match the template",
        "HL-HDR-01": "Category header bullet format is wrong",
        "HL-HDR-02": "Category header bullet format is wrong",
        "HL-HDR-03": "Category header bullet format is wrong",
        "TITLE-01": "Slide title uses the wrong dash style",
    }
    if rule_id in templates:
        return templates[rule_id]
    message = str(violation.get("message") or "").strip()
    if message:
        return _sanitize(message)
    return "This slide needs a layout or formatting fix"


def _where_for_rule(rule_id: str, area: str) -> str:
    where_map = {
        "highlights": "Gray Highlights area",
        "key_activities": "Key Activities table",
        "footer": "Bottom footer band",
        "layout": "Space between Highlights and Key Activities",
        "content": "Slide body text",
        "title": "Slide title",
    }
    if rule_id.startswith("HL-P") or rule_id.startswith("HL-HDR"):
        return "Marked bullet lines in the Highlights area"
    if rule_id == "HL-SPC-02":
        return "Bullet paragraphs in the Highlights area"
    return where_map.get(area, "This slide")


def _fix_steps_for_rule(rule_id: str, violation: dict[str, Any]) -> list[str]:
    fixes: dict[str, list[str]] = {
        "HL-WASTE-01": [
            "Select the Highlights table.",
            "Drag the bottom resize handle up until the text sits near the bottom of the gray box.",
            "Leave only a small margin below the last bullet.",
        ],
        "CONT-HL-01": [
            "On the continuation slide, shrink the Highlights table height to fit the overflow text.",
        ],
        "CONT-SPARSE-01": [
            "Shrink the Highlights table so empty gray space below the bullets is minimal.",
        ],
        "HL-OVERFLOW-01": [
            "Move overflow stories to a continuation slide, or shrink the Highlights table.",
        ],
        "KA-OVERLAP-01": [
            "Move the Key Activities table down, or shorten Highlights so text clears the KA header.",
        ],
        "GEO-02": [
            "Move the Key Activities table up until clear space appears above the footer.",
            "If Highlights text is too long, move content to a continuation slide.",
        ],
        "CONTENT-PRJ-01": [
            "Regenerate the deck from ppt_content.json, or add the missing project slide manually.",
        ],
        "CONTENT-HL-02": [
            "Open ppt_content.json and copy the missing story text into the correct sprint section.",
        ],
        "CONTENT-KA-01": [
            "Select the Key Activities content cell.",
            "Delete leftover sample text and leave blank placeholder bullets only.",
        ],
        "CONTENT-KA-02": [
            "Clear all text from the Key Activities bullets on this slide.",
        ],
        "HL-SPC-02": [
            "Select the affected bullet lines.",
            "Set line spacing to Single, 16 pt (match other project slides).",
        ],
        "HL-P-01": [
            "Select the Highlights header line.",
            "Set font to Manrope Bold and size to 14 pt.",
        ],
        "HL-P-02": [
            "Select the sprint title lines.",
            "Set font to Manrope Light and size to 12 pt.",
        ],
        "HL-P-03": [
            "Select the 'Current week sprint status' line.",
            "Set font to Manrope Light and size to 12 pt.",
        ],
        "HL-P-04": [
            "Select category headers (Completed / Released / In-progress).",
            "Set font to Manrope 12 pt bold with the Wingdings arrow bullet.",
        ],
        "HL-P-05": [
            "Select story bullet lines.",
            "Set font to Manrope Light 12 pt regular weight.",
        ],
        "HL-HDR-01": [
            "Select category header lines.",
            "Apply the G10X Wingdings arrow bullet at outline level 7.",
        ],
        "TITLE-01": [
            "Edit the slide title to use an en dash (–) after 'Delivery status'.",
        ],
    }
    if rule_id in fixes:
        return fixes[rule_id]
    if violation.get("message"):
        return [f"Review and fix: {_sanitize(str(violation['message']))}"]
    return ["Review this slide and correct the issue manually."]


def _why_for_rule(rule_id: str) -> str:
    why_map = {
        "HL-WASTE-01": "Large empty areas make the slide look unfinished.",
        "GEO-02": "Footer overlap makes the deck hard to read when printed or projected.",
        "CONTENT-HL-02": "Missing stories mean the report does not match Jira for this week.",
        "CONTENT-KA-01": "Old template text should not appear in a client-ready deck.",
        "HL-P-05": "Consistent fonts keep the deck aligned with the G10X template.",
        "HL-SPC-02": "Wrong line spacing changes how much text fits on each slide.",
        "KA-OVERLAP-01": "Overlapping text is hard to read and looks unprofessional.",
    }
    return why_map.get(rule_id, "Fixing this keeps the deck consistent and client-ready.")


def _sanitize(text: str) -> str:
    cleaned = re.sub(
        r"\b\d+(\.\d+)?\s*(in|inch|inches|pt|points|emu)\b",
        "",
        text,
        flags=re.I,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;—")
    return cleaned or text


def enrich_finding(violation: dict[str, Any], *, severity: str) -> dict[str, Any]:
    """Add reader-friendly fields while preserving developer metrics."""
    rule_id = str(violation.get("rule_id") or "")
    title = str(violation.get("title") or "")
    slide_index = violation.get("slide_index")
    area = _AREA_BY_RULE.get(rule_id, violation.get("target") or "layout")

    metrics = {
        k: violation[k]
        for k in (
            "actual",
            "limit",
            "limit_in",
            "hl_waste_below_text_in",
            "hl_waste_in",
            "value",
            "expected",
            "ka_bottom_in",
            "footer_limit_in",
            "text_ka_clearance_in",
            "project",
            "story",
            "sample_text",
            "font",
            "size_pt",
            "line_spacing_pt",
            "expected_line_spacing_pt",
        )
        if k in violation and violation[k] is not None
    }
    details = violation.get("details")
    if details and rule_id.startswith(("HL-P", "HL-HDR", "HL-SPC")):
        metrics["paragraphs"] = details[:3] if isinstance(details, list) else details

    return {
        "slide_index": slide_index,
        "slide_number": (slide_index + 1) if slide_index is not None else None,
        "slide_title": title,
        "service": _service_label(title),
        "area": area,
        "rule_id": rule_id,
        "severity": severity,
        "issue": _issue_for_rule(rule_id, violation),
        "where": _where_for_rule(rule_id, area),
        "fix_steps": _fix_steps_for_rule(rule_id, violation),
        "why": _why_for_rule(rule_id),
        "annotation_label": _ANNOT_LABEL_BY_RULE.get(rule_id, "Check here"),
        "metrics": metrics,
        "image": None,
    }
