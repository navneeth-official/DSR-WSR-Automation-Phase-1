"""Per-slide check summaries (every slide, including clean ones) for the validation report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.ppt_hl_typography import _font_matches, _size_matches
from app.services.template_typography import TemplateTypographySpec
from app.validation.severity import normalize_severity

# Which user-facing check family a rule belongs to.
_CHECK_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("typography", ("HL-HDR", "HL-P-", "HL-SPC", "HL-BULLET")),
    ("content", ("CONTENT-",)),
    ("title", ("TITLE-",)),
    ("footer", ("GEO-",)),
    ("key_activities", ("KA-", "CONT-KA")),
    ("highlights_space", ("HL-WASTE", "HL-SIZE", "HL-UTIL", "HL-BOTTOM", "HL-OVERFLOW", "CONT-")),
    ("layout", ("LAYOUT-",)),
)

_SNIPPET_LEN = 90


@dataclass
class SlideCheckInput:
    """Minimal slide + findings bundle accepted by :func:`build_slide_check_summaries`."""

    slide_index: int
    title: str = ""
    violations: list[dict[str, Any]] = field(default_factory=list)


def _check_for_rule(rule_id: str) -> str:
    for name, prefixes in _CHECK_PREFIXES:
        if rule_id.startswith(prefixes):
            return name
    return "other"


def _severity_of(violation: dict[str, Any]) -> str:
    existing = str(violation.get("severity") or "")
    if existing in ("fail", "warn"):
        return existing
    return normalize_severity(violation)


def _snippet(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= _SNIPPET_LEN else text[: _SNIPPET_LEN - 1] + "…"


def _primary_run(paragraph: dict[str, Any]) -> dict[str, Any]:
    runs = paragraph.get("runs") or []
    for run in runs:
        if (run.get("text") or "").strip():
            return run
    return runs[0] if runs else {}


def _audit_paragraphs(
    slide_data: dict[str, Any] | None,
    typography: TemplateTypographySpec | None,
) -> list[dict[str, Any]]:
    """Compare each Highlights paragraph's primary run with the template role style."""
    if not slide_data or typography is None:
        return []
    hl = slide_data.get("highlights") or {}
    rows: list[dict[str, Any]] = []
    for para in hl.get("paragraphs") or []:
        role = str(para.get("role") or "")
        text = para.get("text") or ""
        if not role or role == "blank" or not str(text).strip():
            continue
        spec = typography.role_spec(role)
        run = _primary_run(para)
        font = run.get("font")
        size = run.get("size_pt")
        bold = run.get("bold")

        problems: list[str] = []
        if spec is not None:
            if font and spec.allowed_fonts and not _font_matches(font, spec.allowed_fonts):
                problems.append("font")
            if spec.size_pt is not None and size is not None and not _size_matches(size, spec.size_pt):
                problems.append("size")
            if spec.bold is True and bold is not True:
                problems.append("bold")
            elif spec.bold is False and bold is True:
                problems.append("bold")

        rows.append(
            {
                "role": role,
                "text": _snippet(str(text)),
                "font": font,
                "size_pt": size,
                "bold": bold,
                "expected_font": sorted(spec.allowed_fonts)[0] if spec and spec.allowed_fonts else None,
                "expected_size_pt": spec.size_pt if spec else None,
                "expected_bold": spec.bold if spec else None,
                "ok": not problems,
                "problems": problems,
            }
        )
    return rows


def _slide_value(slide: Any, name: str, default: Any = None) -> Any:
    if isinstance(slide, dict):
        return slide.get(name, default)
    return getattr(slide, name, default)


def build_slide_check_summaries(
    slides: Iterable[Any],
    deck_data: dict[str, Any] | None = None,
    *,
    typography: TemplateTypographySpec | None = None,
    checks_run: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Build one summary per slide.

    ``slides`` holds objects (or dicts) with ``slide_index``, ``title`` and ``violations``
    (raw violations or enriched findings). ``deck_data`` is the extractor output and is
    used to audit typography row-by-row. Slides with no violations still get a summary
    so the UI can show them as green.
    """
    slide_data_by_index: dict[int, dict[str, Any]] = {}
    for item in (deck_data or {}).get("slides", []) or []:
        if item.get("slide_index") is not None:
            slide_data_by_index[int(item["slide_index"])] = item

    summaries: list[dict[str, Any]] = []
    for slide in slides:
        raw_index = _slide_value(slide, "slide_index")
        if raw_index is None:
            continue
        slide_index = int(raw_index)
        violations = list(_slide_value(slide, "violations", []) or [])
        slide_data = slide_data_by_index.get(slide_index)
        title = str(_slide_value(slide, "title", "") or (slide_data or {}).get("title") or "")

        checks: dict[str, dict[str, Any]] = {}
        fail_count = warn_count = 0
        for violation in violations:
            severity = _severity_of(violation)
            if severity == "fail":
                fail_count += 1
            else:
                warn_count += 1
            name = _check_for_rule(str(violation.get("rule_id") or ""))
            entry = checks.setdefault(name, {"status": "pass", "rule_ids": []})
            rule_id = str(violation.get("rule_id") or "")
            if rule_id and rule_id not in entry["rule_ids"]:
                entry["rule_ids"].append(rule_id)
            if severity == "fail":
                entry["status"] = "fail"
            elif entry["status"] != "fail":
                entry["status"] = "warn"

        audited = _audit_paragraphs(slide_data, typography)
        typo = checks.setdefault("typography", {"status": "pass", "rule_ids": []})
        typo["paragraphs_audited"] = audited
        if typo["status"] == "pass" and any(not row["ok"] for row in audited):
            typo["status"] = "warn"

        summaries.append(
            {
                "slide_index": slide_index,
                # slide_index is 1-based (PowerPoint numbering), see extract_deck().
                "slide_number": slide_index,
                "slide_title": title,
                "checks_run": list(checks_run or []),
                "pass": fail_count == 0,
                "fail_count": fail_count,
                "warn_count": warn_count,
                "finding_count": fail_count + warn_count,
                "checks": checks,
                "findings": [
                    {
                        "rule_id": v.get("rule_id"),
                        "severity": _severity_of(v),
                        "issue": v.get("issue") or v.get("message"),
                    }
                    for v in violations
                ],
            }
        )

    summaries.sort(key=lambda s: s["slide_index"])
    return summaries
