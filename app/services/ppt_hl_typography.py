"""Deterministic Highlights (HL) typography validation — font, size, line spacing."""

from __future__ import annotations

from typing import Any

from app.services.template_typography import (
    LINE_SPACING_TOLERANCE_PT,
    SIZE_TOLERANCE_PT,
    RoleStyleSpec,
    TemplateTypographySpec,
)

# Legacy Manrope rulebook (used when no reference template is supplied).
MANROPE_FONTS = frozenset({
    "Manrope",
    "Manrope Light",
    "Manrope Bold",
    "+mn-lt",
    "+mj-lt",
})
STORY_FONTS = frozenset({
    "Manrope Light",
    "+mn-lt",
    "Manrope",
})

HL_HEADER_SIZE_PT = 14.0
HL_BODY_SIZE_PT = 12.0
HL_LINE_SPACING_PT = 16.0
SPC_BEF_TOLERANCE_PT = 0.05

_CATEGORY_ROLES = frozenset({
    "category_completed",
    "category_released",
    "category_inprogress",
    "category_other",
})
_SPACING_ROLES = frozenset({
    "sprint_line",
    "current_week",
    "story_item",
    *_CATEGORY_ROLES,
})


def _size_matches(actual: float | None, expected: float) -> bool:
    if actual is None:
        return True
    return abs(actual - expected) <= SIZE_TOLERANCE_PT


def _font_matches(actual: str | None, allowed: frozenset[str]) -> bool:
    if not actual:
        return True
    actual_norm = actual.strip().lower()
    return any(actual_norm == candidate.strip().lower() for candidate in allowed)


def _primary_run_style(para: dict[str, Any]) -> dict[str, Any]:
    """Dominant font/size/bold from runs (prefer first non-empty text run)."""
    runs = para.get("runs") or []
    for run in runs:
        if (run.get("text") or "").strip():
            return {
                "font": run.get("font"),
                "size_pt": run.get("size_pt"),
                "bold": run.get("bold"),
            }
    if runs:
        run = runs[0]
        return {
            "font": run.get("font"),
            "size_pt": run.get("size_pt"),
            "bold": run.get("bold"),
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
            })
    return styles or [{
        "font": runs[0].get("font"),
        "size_pt": runs[0].get("size_pt"),
        "bold": runs[0].get("bold"),
    }]


def _line_spacing_ok(para: dict[str, Any], expected_pt: float) -> bool:
    pts = para.get("line_spacing_pt")
    if pts is None:
        return True
    return abs(float(pts) - expected_pt) <= LINE_SPACING_TOLERANCE_PT


def _spc_bef_ok(para: dict[str, Any], max_pt: float | None = None) -> bool:
    spc = para.get("spc_bef_pt")
    if spc is None:
        return True
    limit = max_pt if max_pt is not None else SPC_BEF_TOLERANCE_PT
    return float(spc) <= limit


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
    if role in _CATEGORY_ROLES:
        return "HL-P-04"
    if role == "story_item":
        return "HL-P-05"
    return "HL-P-05"


def _expected_font_label(spec: RoleStyleSpec) -> str:
    if spec.allowed_fonts:
        return sorted(spec.allowed_fonts)[0]
    return "template font"


def _check_run_against_spec(
    *,
    run_style: dict[str, Any],
    spec: RoleStyleSpec,
    rule_id: str,
    role: str,
    text: str,
    _add,
    check_bold: bool = True,
) -> None:
    label = _expected_font_label(spec)
    size = spec.size_pt
    msg_base = (
        f"{role.replace('_', ' ')} must match template ({label}"
        + (f" {size:g}pt" if size is not None else "")
        + ")"
    )
    font = run_style.get("font")
    if font and spec.allowed_fonts and not _font_matches(font, spec.allowed_fonts):
        _add(rule_id, "major", msg_base, {
            "role": role,
            "issue": "wrong_font",
            "font": font,
            "expected_fonts": sorted(spec.allowed_fonts),
            "text": _snippet(text),
        })
    run_size = run_style.get("size_pt")
    if size is not None and run_size is not None and not _size_matches(run_size, size):
        _add(rule_id, "major", msg_base, {
            "role": role,
            "issue": "wrong_size",
            "size_pt": run_size,
            "expected_size_pt": size,
            "text": _snippet(text),
        })
    if check_bold and spec.bold is not None:
        actual_bold = run_style.get("bold")
        if actual_bold is not None and actual_bold != spec.bold:
            issue = "not_bold" if spec.bold else "unexpected_bold"
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
) -> list[dict[str, Any]]:
    """
    Validate HL header and content typography.

    When ``typography`` is supplied, expected font/size/spacing come from the
    reference template scan. Otherwise the legacy Manrope rulebook is used.
    """
    if typography is not None:
        return _detect_hl_typography_from_template(
            hl,
            typography,
            slide_index=slide_index,
            title=title,
        )
    return _detect_hl_typography_legacy(hl, slide_index=slide_index, title=title)


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
        if header_spec.size_pt is not None and size is not None and not _size_matches(
            size, header_spec.size_pt
        ):
            _add("HL-HDR-02", "major", header_msg, {
                "issue": "wrong_size",
                "size_pt": size,
                "expected_size_pt": header_spec.size_pt,
            })
        if header_spec.bold is True and bold is False:
            _add("HL-HDR-02", "minor", header_msg, {"issue": "not_bold"})

    for para in hl.get("paragraphs") or []:
        role = para.get("role", "")
        text = para.get("text", "")
        if not text or role == "blank":
            continue

        spec = typography.role_spec(str(role))
        rule_id = _role_rule_id(str(role))
        if spec is None:
            continue

        styles = _all_runs_style(para) if role == "sprint_line" else [_primary_run_style(para)]
        for index, run_style in enumerate(styles):
            _check_run_against_spec(
                run_style=run_style,
                spec=spec,
                rule_id=rule_id,
                role=str(role),
                text=text,
                _add=_add,
                check_bold=role != "sprint_line" or index == 0,
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
                    "role": role,
                    "issue": "spc_bef_nonzero",
                    "spc_bef_pt": para.get("spc_bef_pt"),
                    "expected_max_spc_bef_pt": spec.max_spc_bef_pt,
                    "text": _snippet(text),
                })

    return violations


def _detect_hl_typography_legacy(
    hl: dict[str, Any],
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

    header = hl.get("header_metrics") or {}
    for run in header.get("runs") or []:
        font = run.get("font")
        size = run.get("size_pt")
        bold = run.get("bold")
        if font and not _font_matches(font, MANROPE_FONTS):
            _add(
                "HL-HDR-02",
                "major",
                "Highlights header must use Manrope Bold 14pt",
                {"issue": "wrong_font", "font": font, "expected_font": "Manrope"},
            )
        if size is not None and not _size_matches(size, HL_HEADER_SIZE_PT):
            _add(
                "HL-HDR-02",
                "major",
                "Highlights header must use Manrope Bold 14pt",
                {"issue": "wrong_size", "size_pt": size, "expected_size_pt": HL_HEADER_SIZE_PT},
            )
        if bold is False:
            _add(
                "HL-HDR-02",
                "minor",
                "Highlights header must use Manrope Bold 14pt",
                {"issue": "not_bold", "expected_bold": True},
            )

    for para in hl.get("paragraphs") or []:
        role = para.get("role", "")
        text = para.get("text", "")
        if not text or role == "blank":
            continue

        style = _primary_run_style(para)

        if role == "project_name":
            if style.get("font") and not _font_matches(style["font"], MANROPE_FONTS):
                _add("HL-P-01", "major", "Project label must use Manrope 12pt bold", {
                    "role": role, "issue": "wrong_font", "font": style["font"],
                    "text": _snippet(text),
                })
            if style.get("size_pt") is not None and not _size_matches(style["size_pt"], HL_BODY_SIZE_PT):
                _add("HL-P-01", "major", "Project label must use Manrope 12pt bold", {
                    "role": role, "issue": "wrong_size", "size_pt": style["size_pt"],
                    "text": _snippet(text),
                })
            if style.get("bold") is False:
                _add("HL-P-01", "minor", "Project label must use Manrope 12pt bold", {
                    "role": role, "issue": "not_bold", "text": _snippet(text),
                })

        elif role == "sprint_line":
            for run_style in _all_runs_style(para):
                if run_style.get("font") and not _font_matches(run_style["font"], MANROPE_FONTS):
                    _add("HL-P-02", "major", "Sprint line must use Manrope / Manrope Light 12pt", {
                        "role": role, "issue": "wrong_font", "font": run_style["font"],
                        "text": _snippet(text),
                    })
                if run_style.get("size_pt") is not None and not _size_matches(
                    run_style["size_pt"], HL_BODY_SIZE_PT
                ):
                    _add("HL-P-02", "major", "Sprint line must use Manrope / Manrope Light 12pt", {
                        "role": role, "issue": "wrong_size", "size_pt": run_style["size_pt"],
                        "text": _snippet(text),
                    })

        elif role == "current_week":
            if style.get("font") and not _font_matches(style["font"], MANROPE_FONTS):
                _add("HL-P-03", "major", "Current week status must use Manrope Light 12pt", {
                    "role": role, "issue": "wrong_font", "font": style["font"],
                    "text": _snippet(text),
                })
            if style.get("size_pt") is not None and not _size_matches(style["size_pt"], HL_BODY_SIZE_PT):
                _add("HL-P-03", "major", "Current week status must use Manrope Light 12pt", {
                    "role": role, "issue": "wrong_size", "size_pt": style["size_pt"],
                    "text": _snippet(text),
                })

        elif role in _CATEGORY_ROLES:
            if style.get("font") and not _font_matches(style["font"], MANROPE_FONTS):
                _add("HL-P-04", "major", "Category header must use Manrope 12pt bold", {
                    "role": role, "issue": "wrong_font", "font": style["font"],
                    "text": _snippet(text),
                })
            if style.get("size_pt") is not None and not _size_matches(style["size_pt"], HL_BODY_SIZE_PT):
                _add("HL-P-04", "major", "Category header must use Manrope 12pt bold", {
                    "role": role, "issue": "wrong_size", "size_pt": style["size_pt"],
                    "text": _snippet(text),
                })
            if style.get("bold") is False:
                _add("HL-P-04", "minor", "Category header must use Manrope 12pt bold", {
                    "role": role, "issue": "not_bold", "text": _snippet(text),
                })

        elif role == "story_item":
            if style.get("font") and not _font_matches(style["font"], STORY_FONTS):
                _add("HL-P-05", "major", "Story line must use Manrope Light 12pt", {
                    "role": role, "issue": "wrong_font", "font": style["font"],
                    "text": _snippet(text),
                })
            if style.get("size_pt") is not None and not _size_matches(style["size_pt"], HL_BODY_SIZE_PT):
                _add("HL-P-05", "major", "Story line must use Manrope Light 12pt", {
                    "role": role, "issue": "wrong_size", "size_pt": style["size_pt"],
                    "text": _snippet(text),
                })
            if style.get("bold") is True:
                _add("HL-P-05", "minor", "Story line must use Manrope Light 12pt regular weight", {
                    "role": role, "issue": "unexpected_bold", "text": _snippet(text),
                })
            if not _spc_bef_ok(para):
                _add("HL-SPC-04", "minor", "Story bullets must not add space-before", {
                    "role": role, "issue": "spc_bef_nonzero",
                    "spc_bef_pt": para.get("spc_bef_pt"), "text": _snippet(text),
                })

        if role in _SPACING_ROLES:
            if not _line_spacing_ok(para, HL_LINE_SPACING_PT):
                _add(
                    "HL-SPC-02",
                    "major",
                    f"HL line spacing must be {HL_LINE_SPACING_PT:g}pt (template single spacing)",
                    {
                        "role": role,
                        "issue": "wrong_line_spacing",
                        "line_spacing_pt": para.get("line_spacing_pt"),
                        "expected_line_spacing_pt": HL_LINE_SPACING_PT,
                        "text": _snippet(text),
                    },
                )

    return violations


def summarize_hl_typography(hl: dict[str, Any]) -> dict[str, Any]:
    """Compact typography summary for visual AI context."""
    header = hl.get("header_metrics") or {}
    header_run = (header.get("runs") or [{}])[0]
    paras = [p for p in (hl.get("paragraphs") or []) if p.get("text") and p.get("role") != "blank"]

    fonts: set[str] = set()
    sizes: set[float] = set()
    line_spacings: set[float] = set()
    for para in paras:
        for run in para.get("runs") or []:
            if run.get("font"):
                fonts.add(str(run["font"]))
            if run.get("size_pt") is not None:
                sizes.add(float(run["size_pt"]))
        if para.get("line_spacing_pt") is not None:
            line_spacings.add(float(para["line_spacing_pt"]))

    violations = detect_hl_typography_violations(hl)
    return {
        "header_font": header_run.get("font"),
        "header_size_pt": header_run.get("size_pt"),
        "header_bold": header_run.get("bold"),
        "body_fonts": sorted(fonts),
        "body_sizes_pt": sorted(sizes),
        "line_spacings_pt": sorted(line_spacings),
        "expected_header": {"font": "Manrope", "size_pt": HL_HEADER_SIZE_PT, "bold": True},
        "expected_body": {"fonts": sorted(MANROPE_FONTS), "size_pt": HL_BODY_SIZE_PT},
        "expected_line_spacing_pt": HL_LINE_SPACING_PT,
        "typography_violation_count": len(violations),
        "typography_rule_ids": sorted({v["rule_id"] for v in violations}),
    }
