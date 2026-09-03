"""Human-readable typography labels for validation reports."""

from __future__ import annotations

from typing import Any

_THEME_FONT_LABELS: dict[str, str] = {
    "+mn-lt": "Calibri",
    "+mj-lt": "Calibri",
    "calibri light": "Calibri Light",
}

_ROLE_LABELS: dict[str, str] = {
    "project_name": "Project name",
    "sprint_line": "Sprint title",
    "current_week": "Current week status",
    "category_completed": "Category — Completed",
    "category_released": "Category — Released",
    "category_inprogress": "Category — In progress",
    "category_other": "Category header",
    "story_item": "Story bullet",
    "other": "Story bullet",
}


def human_role_label(role: str, label_spec: Any | None = None) -> str:
    if label_spec is not None:
        if role == "current_week":
            return label_spec.current_week_display().title()
        if role.startswith("category_"):
            return label_spec.category_display(role).title()
        if role == "sprint_line":
            return "Sprint line"
        if role == "story_item":
            return "Story bullet"
    return _ROLE_LABELS.get(role, role.replace("_", " ").title())


def display_font_name(font: str | None) -> str:
    if not font:
        return "Unknown"
    key = font.strip().lower()
    if key in _THEME_FONT_LABELS:
        return _THEME_FONT_LABELS[key]
    return font.strip()


def display_font_list(fonts: list[str] | None) -> str:
    if not fonts:
        return "Template font"
    seen: list[str] = []
    for font in fonts:
        label = display_font_name(font)
        if label not in seen:
            seen.append(label)
    return " or ".join(seen)


def display_weight(bold: bool | None) -> str:
    if bold is True:
        return "Bold"
    if bold is False:
        return "Regular"
    return "Regular (bold not set)"


def display_style(font: str | None, size_pt: float | None, bold: bool | None) -> str:
    parts: list[str] = [display_font_name(font)]
    if size_pt is not None:
        parts.append(f"{size_pt:g} pt")
    parts.append(display_weight(bold))
    return ", ".join(parts)


def expected_style(
    fonts: list[str] | None,
    size_pt: float | None,
    bold: bool | None,
) -> str:
    parts: list[str] = [display_font_list(fonts)]
    if size_pt is not None:
        parts.append(f"{size_pt:g} pt")
    if bold is True:
        parts.append("Bold")
    elif bold is False:
        parts.append("Regular")
    return ", ".join(parts)


def _issue_labels(issues: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for issue in issues:
        kind = str(issue.get("issue") or "")
        if kind == "wrong_font":
            labels.append(
                f"Wrong font (use {display_font_list(issue.get('expected_fonts'))})"
            )
        elif kind == "wrong_size":
            labels.append(f"Wrong size (use {issue.get('expected_size_pt')} pt)")
        elif kind == "not_bold":
            labels.append("Turn on Bold")
        elif kind == "unexpected_bold":
            labels.append("Turn off Bold")
        elif kind == "wrong_line_spacing":
            labels.append(
                f"Fix line spacing (use {issue.get('expected_line_spacing_pt')} pt)"
            )
        elif kind == "wrong_color":
            expected = issue.get("expected_colors") or []
            labels.append(f"Wrong color (use {display_color_list(expected)})")
    return labels


def display_color_list(colors: list[str] | None) -> str:
    if not colors:
        return "template color"
    seen: list[str] = []
    for color in colors:
        label = color
        if color.startswith("scheme:"):
            label = f"theme {color.replace('scheme:', '')}"
        elif not color.startswith("#"):
            label = f"#{color}"
        if label not in seen:
            seen.append(label)
    return " or ".join(seen)


def enrich_paragraph_row(
    row: dict[str, Any],
    typo_violations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach status and plain-language fix hints to an audited paragraph row."""
    role = str(row.get("role") or "")
    preview = str(row.get("text_preview") or "")
    row_index = row.get("paragraph_index")
    matched_issues: list[dict[str, Any]] = []
    for violation in typo_violations:
        for detail in violation.get("details") or []:
            if str(detail.get("role") or "") != role:
                continue
            detail_index = detail.get("paragraph_index")
            if detail_index is not None and row_index is not None:
                if int(detail_index) != int(row_index):
                    continue
            elif detail_index is not None or row_index is not None:
                detail_text = str(detail.get("text") or "").strip()
                paragraph_text = str(detail.get("paragraph_text") or preview).strip()
                if detail_text and detail_text not in paragraph_text:
                    continue
            else:
                detail_text = str(detail.get("text") or "").strip()
                if detail_text and preview and detail_text not in preview:
                    if not preview.startswith(detail_text[:20]):
                        continue
            matched_issues.append(detail)

    issue_labels = _issue_labels(matched_issues)
    status = "fix" if issue_labels else "ok"
    fix_hint = issue_labels[0] if issue_labels else "No change needed"
    if len(issue_labels) > 1:
        fix_hint = "; ".join(issue_labels)

    actual_style = row.get("actual_style") or display_style(
        row.get("font"), row.get("size_pt"), row.get("bold")
    )
    if matched_issues:
        bad = matched_issues[0]
        if bad.get("issue") == "wrong_font":
            actual_style = f"{bad.get('font')} (wrong — use {display_font_list(bad.get('expected_fonts'))})"

    return {
        **row,
        "line_type": human_role_label(role),
        "actual_style": actual_style,
        "expected_style": expected_style(
            row.get("expected_fonts"),
            row.get("expected_size_pt"),
            row.get("expected_bold"),
        ),
        "status": status,
        "fix_hint": fix_hint,
        "issues": issue_labels,
    }


def dedupe_paragraph_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("role") or ""), str(row.get("text_preview") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out
