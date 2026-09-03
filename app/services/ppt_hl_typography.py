"""Deterministic Highlights (HL) typography validation — template is ground truth."""

from __future__ import annotations

from typing import Any

from app.services.template_typography import (
    LINE_SPACING_TOLERANCE_PT,
    SIZE_TOLERANCE_PT,
    RoleStyleSpec,
    TemplateTypographySpec,
    allowed_sizes_for_spec,
    size_matches_spec,
)

_INSIGNIFICANT_FONT_RUN_MAX_LEN = 4


def _norm_color(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if text.lower().startswith("scheme:"):
        return text.lower()
    return text.upper()


def _size_matches(actual: float | None, expected: float) -> bool:
    if actual is None:
        return True
    return abs(actual - expected) <= SIZE_TOLERANCE_PT


def _font_matches(actual: str | None, allowed: frozenset[str]) -> bool:
    if not actual:
        return True
    actual_norm = actual.strip().lower()
    return any(actual_norm == candidate.strip().lower() for candidate in allowed)


def _color_matches(actual: str | None, allowed: frozenset[str]) -> bool:
    if not allowed:
        return True
    if not actual:
        return True
    norm = _norm_color(actual)
    allowed_norm = {_norm_color(c) for c in allowed if c}
    return norm in allowed_norm


def _primary_run_style(para: dict[str, Any]) -> dict[str, Any]:
    """Dominant font/size/bold from runs (prefer first non-empty text run)."""
    runs = para.get("runs") or []
    for run in runs:
        if (run.get("text") or "").strip():
            return {
                "font": run.get("font"),
                "size_pt": run.get("size_pt"),
                "bold": run.get("bold"),
                "italic": run.get("italic"),
                "color": run.get("color"),
            }
    if runs:
        run = runs[0]
        return {
            "font": run.get("font"),
            "size_pt": run.get("size_pt"),
            "bold": run.get("bold"),
            "italic": run.get("italic"),
            "color": run.get("color"),
        }
    return {}


def _all_runs_style(para: dict[str, Any]) -> list[dict[str, Any]]:
    runs = para.get("runs") or []
    if not runs:
        return []
    styles = []
    for run in runs:
        if (run.get("text") or "").strip() or len(runs) == 1:
            styles.append({
                "font": run.get("font"),
                "size_pt": run.get("size_pt"),
                "bold": run.get("bold"),
                "italic": run.get("italic"),
                "color": run.get("color"),
                "text": run.get("text"),
            })
    return styles or [{
        "font": runs[0].get("font"),
        "size_pt": runs[0].get("size_pt"),
        "bold": runs[0].get("bold"),
        "italic": runs[0].get("italic"),
        "color": runs[0].get("color"),
    }]


def _line_spacing_ok(para: dict[str, Any], expected_pt: float) -> bool:
    pts = para.get("line_spacing_pt")
    if pts is None:
        return True
    return abs(float(pts) - expected_pt) <= LINE_SPACING_TOLERANCE_PT


def _spc_bef_ok(para: dict[str, Any], max_pt: float | None) -> bool:
    spc = para.get("spc_bef_pt")
    if spc is None or max_pt is None:
        return True
    return float(spc) <= max_pt


def _snippet(text: str, limit: int = 60) -> str:
    t = (text or "").strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _role_rule_id(role: str) -> str:
    if role == "project_name":
        return "HL-P-01"
    if role == "sprint_line":
        return "HL-P-02"
    if role == "current_week":
        return "HL-P-03"
    if role.startswith("category_"):
        return "HL-P-04"
    if role == "story_item":
        return "HL-P-05"
    return "HL-P-05"


def _expected_font_label(spec: RoleStyleSpec) -> str:
    if spec.allowed_fonts:
        return sorted(spec.allowed_fonts)[0]
    return "template font"


def _display_color_label(colors: frozenset[str]) -> str:
    if not colors:
        return "template color"
    labels = []
    for color in sorted(colors):
        if color.startswith("scheme:"):
            labels.append(color.replace("scheme:", "theme "))
        else:
            labels.append(f"#{color}")
    return " or ".join(labels)


def _is_insignificant_font_run(
    run_text: str,
    para_text: str,
    *,
    font: str | None = None,
    allowed_fonts: frozenset[str] | None = None,
) -> bool:
    """Skip tiny glue-word runs only when font family is still on-template."""
    token = (run_text or "").strip()
    if len(token) > _INSIGNIFICANT_FONT_RUN_MAX_LEN:
        return False
    if not token:
        return True
    if font and allowed_fonts and not _font_matches(font, allowed_fonts):
        return False
    return len((para_text or "").strip()) > 20


def _sprint_stats_run_index(styles: list[dict[str, Any]]) -> int | None:
    """Index of the first run containing '(' — stats portion starts here in template."""
    for index, run_style in enumerate(styles):
        if "(" in str(run_style.get("text") or ""):
            return index
    return None


def _sprint_run_should_be_bold(run_index: int, stats_run_index: int | None) -> bool:
    if stats_run_index is None:
        return run_index == 0
    return run_index < stats_run_index


def _check_sprint_mixed_bold(
    *,
    styles: list[dict[str, Any]],
    rule_id: str,
    role: str,
    text: str,
    detail_context: dict[str, Any],
    _add,
) -> None:
    stats_idx = _sprint_stats_run_index(styles)
    if stats_idx is None:
        return
    for index, run_style in enumerate(styles):
        run_text = str(run_style.get("text") or "")
        if not run_text.strip():
            continue
        expected_bold = _sprint_run_should_be_bold(index, stats_idx)
        actual_bold = run_style.get("bold")
        if actual_bold is None:
            actual_bold = False
        if actual_bold == expected_bold:
            continue
        issue = "unexpected_bold" if actual_bold else "not_bold"
        _add(
            rule_id,
            "minor",
            "Sprint line must match template bold split (title bold, dates/stats regular)",
            {
                **detail_context,
                "role": role,
                "issue": issue,
                "text": _snippet(run_text.strip() or text),
            },
        )
        return


def _check_run_against_spec(
    *,
    run_style: dict[str, Any],
    spec: RoleStyleSpec,
    rule_id: str,
    role: str,
    text: str,
    para_text: str,
    _add,
    check_bold: bool = True,
    check_italic: bool = True,
    check_font: bool = True,
) -> None:
    label = _expected_font_label(spec)
    size = spec.size_pt
    msg_base = (
        f"{role.replace('_', ' ')} must match template ({label}"
        + (f" {size:g}pt" if size is not None else "")
        + ")"
    )
    font = run_style.get("font")
    if (
        check_font
        and font
        and spec.allowed_fonts
        and not _font_matches(font, spec.allowed_fonts)
        and not _is_insignificant_font_run(
            text,
            para_text,
            font=font,
            allowed_fonts=spec.allowed_fonts,
        )
    ):
        _add(rule_id, "major", msg_base, {
            "role": role,
            "issue": "wrong_font",
            "font": font,
            "expected_fonts": sorted(spec.allowed_fonts),
            "text": _snippet(text),
        })
    run_size = run_style.get("size_pt")
    if run_size is not None and not size_matches_spec(run_size, spec):
        _add(rule_id, "major", msg_base, {
            "role": role,
            "issue": "wrong_size",
            "size_pt": run_size,
            "expected_size_pt": spec.size_pt,
            "expected_sizes_pt": sorted(allowed_sizes_for_spec(spec)),
            "text": _snippet(text),
        })
    color = run_style.get("color")
    if color and spec.allowed_colors and not _color_matches(color, spec.allowed_colors):
        _add(rule_id, "major", msg_base, {
            "role": role,
            "issue": "wrong_color",
            "color": color,
            "expected_colors": sorted(spec.allowed_colors),
            "text": _snippet(text),
        })
    if check_bold and spec.bold is not None:
        actual_bold = run_style.get("bold")
        if actual_bold is None:
            actual_bold = False
        if actual_bold != spec.bold:
            issue = "not_bold" if spec.bold else "unexpected_bold"
            _add(rule_id, "minor", msg_base, {
                "role": role,
                "issue": issue,
                "text": _snippet(text),
                "expected_fonts": sorted(spec.allowed_fonts),
                "expected_size_pt": spec.size_pt,
            })
    if check_italic and spec.italic is not None:
        actual_italic = run_style.get("italic")
        if actual_italic is None:
            actual_italic = False
        if actual_italic != spec.italic:
            issue = "not_italic" if spec.italic else "unexpected_italic"
            _add(rule_id, "minor", msg_base, {
                "role": role,
                "issue": issue,
                "text": _snippet(text),
            })


def detect_hl_typography_violations(
    hl: dict[str, Any],
    *,
    slide_index: int | None = None,
    title: str = "",
    typography: TemplateTypographySpec | None = None,
    spacing: Any | None = None,
) -> list[dict[str, Any]]:
    """
    Validate HL header and content typography against the reference template.

    Expected font, size, weight, color, and spacing come from ``typography``.
    When ``typography`` is omitted, no typography rules are applied.
    """
    if typography is None:
        return []
    violations = _detect_hl_typography_from_template(
        hl,
        typography,
        slide_index=slide_index,
        title=title,
    )
    if spacing is not None:
        from app.services.template_spacing_spec import detect_hl_spacing_violations

        violations.extend(
            detect_hl_spacing_violations(
                hl,
                spacing=spacing,
                slide_index=slide_index,
                title=title,
            )
        )
    return violations


def _detect_hl_typography_from_template(
    hl: dict[str, Any],
    typography: TemplateTypographySpec,
    *,
    slide_index: int | None = None,
    title: str = "",
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    details_by_rule: dict[str, list[dict[str, Any]]] = {}

    def _add(rule_id: str, severity: str, message: str, detail: dict[str, Any]) -> None:
        details_by_rule.setdefault(rule_id, []).append(detail)
        if rule_id not in {v["rule_id"] for v in violations}:
            violations.append({
                "rule_id": rule_id,
                "severity": severity,
                "slide_index": slide_index,
                "title": title,
                "message": message,
                "details": details_by_rule[rule_id],
            })
        else:
            for v in violations:
                if v["rule_id"] == rule_id:
                    v["details"] = details_by_rule[rule_id]
                    break

    header_spec = typography.header
    header = hl.get("header_metrics") or {}
    header_label = _expected_font_label(header_spec)
    header_msg = (
        f"Highlights header must match template ({header_label}"
        + (f" {header_spec.size_pt:g}pt" if header_spec.size_pt else "")
        + ")"
    )
    for run in header.get("runs") or []:
        font = run.get("font")
        size = run.get("size_pt")
        bold = run.get("bold")
        if font and header_spec.allowed_fonts and not _font_matches(font, header_spec.allowed_fonts):
            _add("HL-HDR-02", "major", header_msg, {
                "issue": "wrong_font",
                "font": font,
                "expected_fonts": sorted(header_spec.allowed_fonts),
            })
        if header_spec.size_pt is not None and size is not None and not size_matches_spec(
            size, header_spec
        ):
            _add("HL-HDR-02", "major", header_msg, {
                "issue": "wrong_size",
                "size_pt": size,
                "expected_size_pt": header_spec.size_pt,
                "expected_sizes_pt": sorted(allowed_sizes_for_spec(header_spec)),
            })
        color = run.get("color")
        if color and header_spec.allowed_colors and not _color_matches(color, header_spec.allowed_colors):
            _add("HL-HDR-02", "major", header_msg, {
                "issue": "wrong_color",
                "color": color,
                "expected_colors": sorted(header_spec.allowed_colors),
            })
        if header_spec.bold is True:
            header_bold = bold if bold is not None else False
            if header_bold is False:
                _add("HL-HDR-02", "minor", header_msg, {"issue": "not_bold"})

    for paragraph_index, para in enumerate(hl.get("paragraphs") or []):
        role = para.get("role", "")
        text = para.get("text", "")
        if not text or role == "blank":
            continue

        spec = typography.role_spec(str(role))
        rule_id = _role_rule_id(str(role))
        if spec is None:
            continue

        detail_context = {
            "paragraph_index": paragraph_index,
            "paragraph_text": _snippet(text, 120),
        }

        styles = _all_runs_style(para)
        if role == "sprint_line":
            _check_sprint_mixed_bold(
                styles=styles,
                rule_id=rule_id,
                role=str(role),
                text=text,
                detail_context=detail_context,
                _add=lambda rid, sev, msg, detail: _add(
                    rid,
                    sev,
                    msg,
                    {**detail_context, **detail},
                ),
            )
        for index, run_style in enumerate(styles):
            run_text = run_style.get("text") or text
            check_bold = index == 0 and role != "sprint_line"
            if role == "story_item" and spec.bold is False:
                check_bold = True
            _check_run_against_spec(
                run_style=run_style,
                spec=spec,
                rule_id=rule_id,
                role=str(role),
                text=run_text,
                para_text=text,
                _add=lambda rid, sev, msg, detail: _add(
                    rid,
                    sev,
                    msg,
                    {**detail_context, **detail},
                ),
                check_bold=check_bold,
                check_italic=(index == 0),
            )

        if (
            spec.line_spacing_pt is not None
            and para.get("line_spacing_pt") is not None
            and not _line_spacing_ok(para, spec.line_spacing_pt)
        ):
            _add(
                "HL-SPC-02",
                "major",
                f"Line spacing must match template ({spec.line_spacing_pt:g}pt)",
                {
                    **detail_context,
                    "role": role,
                    "issue": "wrong_line_spacing",
                    "line_spacing_pt": para.get("line_spacing_pt"),
                    "expected_line_spacing_pt": spec.line_spacing_pt,
                    "text": _snippet(text),
                },
            )

        if role == "story_item" and spec.max_spc_bef_pt is not None:
            if not _spc_bef_ok(para, spec.max_spc_bef_pt):
                _add("HL-SPC-04", "minor", "Story spacing exceeds template", {
                    **detail_context,
                    "role": role,
                    "issue": "spc_bef_nonzero",
                    "spc_bef_pt": para.get("spc_bef_pt"),
                    "expected_max_spc_bef_pt": spec.max_spc_bef_pt,
                    "text": _snippet(text),
                })

    return violations


def summarize_hl_typography(
    hl: dict[str, Any],
    *,
    typography: TemplateTypographySpec | None = None,
) -> dict[str, Any]:
    """Compact typography summary for visual AI context."""
    header = hl.get("header_metrics") or {}
    header_run = (header.get("runs") or [{}])[0]
    paras = [p for p in (hl.get("paragraphs") or []) if p.get("text") and p.get("role") != "blank"]

    fonts: set[str] = set()
    sizes: set[float] = set()
    colors: set[str] = set()
    line_spacings: set[float] = set()
    for para in paras:
        for run in para.get("runs") or []:
            if run.get("font"):
                fonts.add(str(run["font"]))
            if run.get("size_pt") is not None:
                sizes.add(float(run["size_pt"]))
            if run.get("color"):
                colors.add(str(run["color"]))
        if para.get("line_spacing_pt") is not None:
            line_spacings.add(float(para["line_spacing_pt"]))

    violations = detect_hl_typography_violations(hl, typography=typography)
    summary: dict[str, Any] = {
        "header_font": header_run.get("font"),
        "header_size_pt": header_run.get("size_pt"),
        "header_bold": header_run.get("bold"),
        "body_fonts": sorted(fonts),
        "body_sizes_pt": sorted(sizes),
        "body_colors": sorted(colors),
        "line_spacings_pt": sorted(line_spacings),
        "typography_violation_count": len(violations),
        "typography_rule_ids": sorted({v["rule_id"] for v in violations}),
    }
    if typography is not None:
        story = typography.role_spec("story_item") or typography.role_spec("other")
        summary["expected_header"] = {
            "fonts": sorted(typography.header.allowed_fonts),
            "size_pt": typography.header.size_pt,
            "bold": typography.header.bold,
            "colors": sorted(typography.header.allowed_colors),
        }
        if story is not None:
            summary["expected_body"] = {
                "fonts": sorted(story.allowed_fonts),
                "size_pt": story.size_pt,
                "bold": story.bold,
                "colors": sorted(story.allowed_colors),
                "line_spacing_pt": story.line_spacing_pt,
            }
    return summary
