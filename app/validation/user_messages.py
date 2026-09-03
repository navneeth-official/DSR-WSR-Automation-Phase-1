"""Plain-language issue text and fix steps for validation findings."""

from __future__ import annotations

import re
from app.validation.typography_display import display_font_list, human_role_label

_AREA_BY_RULE: dict[str, str] = {
    "HL-WASTE-01": "highlights",
    "HL-TOP-WASTE-01": "highlights",
    "HL-BOTTOM-WASTE-01": "highlights",
    "HL-UTIL-01": "highlights",
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
    "KA-TOP-WASTE-01": "key_activities",
    "KA-BOTTOM-WASTE-01": "key_activities",
    "KA-UTIL-01": "key_activities",
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
    "HL-TOP-WASTE-01": "Unused top space",
    "HL-BOTTOM-WASTE-01": "Unused bottom space",
    "HL-UTIL-01": "Under-used area",
    "CONT-HL-01": "Empty space here",
    "CONT-SPARSE-01": "Empty space here",
    "HL-SIZE-01": "Empty space here",
    "KA-TOP-WASTE-01": "Unused top space",
    "KA-BOTTOM-WASTE-01": "Unused bottom space",
    "KA-UTIL-01": "Under-used area",
    "KA-SIZE-01": "Empty space here",
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


def _typography_detail_issue(detail: dict[str, Any]) -> str:
    role = human_role_label(str(detail.get("role") or "text"))
    issue = str(detail.get("issue") or "")
    text = detail.get("text")
    snippet = f" ('{text}')" if text else ""
    if issue == "wrong_font":
        expected = detail.get("expected_fonts") or [detail.get("expected_font")]
        expected_txt = ", ".join(str(x) for x in expected if x)
        return f"Wrong font on {role}{snippet}: got '{detail.get('font')}', expected {expected_txt}"
    if issue == "wrong_size":
        return (
            f"Wrong size on {role}{snippet}: got {detail.get('size_pt')}pt, "
            f"expected {detail.get('expected_size_pt')}pt"
        )
    if issue == "not_bold":
        return f"Missing bold on {role}{snippet} (template requires bold)"
    if issue == "unexpected_bold":
        return f"Unexpected bold on {role}{snippet} (template requires regular weight)"
    if issue == "wrong_line_spacing":
        return (
            f"Wrong line spacing on {role}{snippet}: got {detail.get('line_spacing_pt')}pt, "
            f"expected {detail.get('expected_line_spacing_pt')}pt"
        )
    if issue == "wrong_color":
        expected = detail.get("expected_colors") or []
        expected_txt = ", ".join(str(x) for x in expected if x)
        return f"Wrong color on {role}{snippet}: got '{detail.get('color')}', expected {expected_txt}"
    if issue == "extra_blanks_after_current_week":
        return (
            f"Extra blank line(s) after Current week sprint status "
            f"({detail.get('blank_count')} found, template allows {detail.get('expected_max')})"
        )
    if issue == "extra_sprint_gap_blanks":
        return (
            f"Extra blank line(s) before the next sprint block "
            f"({detail.get('blank_count')} found, template allows {detail.get('expected_max')})"
        )
    if issue == "sprint_line_spc_bef_high":
        return (
            f"Sprint line top spacing is too large "
            f"({detail.get('spc_bef_pt')} pt, template {detail.get('expected_max_spc_bef_pt')} pt)"
        )
    return ""


def _issue_for_rule(rule_id: str, violation: dict[str, Any]) -> str:
    templates: dict[str, str] = {
        "HL-WASTE-01": "Too much empty space in the Highlights box",
        "HL-TOP-WASTE-01": "Unused empty space at the top of the Highlights box",
        "HL-BOTTOM-WASTE-01": "Unused empty space at the bottom of the Highlights box",
        "HL-UTIL-01": "Highlights box is larger than needed for the content",
        "CONT-HL-01": "Highlights continuation box is taller than needed",
        "CONT-SPARSE-01": "Highlights box is too tall for the amount of text",
        "KA-TOP-WASTE-01": "Unused empty space at the top of the Key Activities box",
        "KA-BOTTOM-WASTE-01": "Unused empty space at the bottom of the Key Activities box",
        "KA-UTIL-01": "Key Activities box is larger than needed for the items",
        "HL-OVERFLOW-01": "Highlights text runs outside its gray box",
        "KA-OVERLAP-01": "Highlights text overlaps the Key Activities area",
        "GEO-02": "Content is too close to or crosses the footer area",
        "CONTENT-PRJ-01": "A project from this week's report is missing from the deck",
        "CONTENT-HL-02": "A story from this week's report is missing on the slide",
        "CONTENT-KA-01": "Key Activities still shows old sample or leftover text",
        "CONTENT-KA-02": "Key Activities should be empty but contains text",
        "HL-SPC-02": "Line spacing between bullets does not match the template",
        "HL-SPC-03": "Extra spacing between sprint blocks does not match the template",
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
    details = violation.get("details")
    if rule_id.startswith(("HL-P", "HL-HDR", "HL-SPC")) and isinstance(details, list) and details:
        detail_issue = _typography_detail_issue(details[0])
        if detail_issue:
            return detail_issue
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


def _typography_fix_steps(violation: dict[str, Any]) -> list[str] | None:
    details = violation.get("details")
    if not isinstance(details, list) or not details:
        return None
    detail = details[0]
    issue = str(detail.get("issue") or "")
    role = str(detail.get("role") or "text").replace("_", " ")
    expected_fonts = detail.get("expected_fonts") or []
    font_hint = display_font_list(expected_fonts)
    size = detail.get("expected_size_pt")
    size_hint = f" and size to {size:g} pt" if size is not None else ""
    if issue == "wrong_font":
        return [f"Select the {role} line.", f"Set font to {font_hint}{size_hint}."]
    if issue == "wrong_size":
        return [f"Select the {role} line.", f"Set size to {size:g} pt (font: {font_hint})."]
    if issue == "not_bold":
        return [f"Select the {role} line.", f"Apply bold ({font_hint}{size_hint})."]
    if issue == "unexpected_bold":
        return [f"Select the {role} line.", f"Remove bold — use regular weight ({font_hint}{size_hint})."]
    if issue == "wrong_line_spacing":
        expected = detail.get("expected_line_spacing_pt")
        return [
            f"Select the {role} line.",
            f"Set line spacing to {expected:g} pt to match the template.",
        ]
    return None


def _fix_steps_for_rule(rule_id: str, violation: dict[str, Any]) -> list[str]:
    typo_steps = _typography_fix_steps(violation)
    if typo_steps:
        return typo_steps
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
            "Set line spacing to match the template (see validation metrics for expected pt).",
        ],
        "HL-TOP-WASTE-01": [
            "Select the Highlights table.",
            "Move content up or shrink the box to reduce empty space at the top.",
        ],
        "HL-BOTTOM-WASTE-01": [
            "Select the Highlights table.",
            "Drag the bottom resize handle up until the text sits near the bottom of the gray box.",
        ],
        "HL-UTIL-01": [
            "Select the Highlights table.",
            "Resize the table height to match the amount of content.",
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
        return [str(violation["message"]).strip()]
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
        "slide_number": slide_index,
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
