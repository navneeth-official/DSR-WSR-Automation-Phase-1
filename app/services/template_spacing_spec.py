"""Template-learned HL paragraph spacing bands for validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pptx.oxml.ns import qn

from app.services.template_block_spec import TemplateBlockSpec, load_block_spec
from app.services.template_typography import SPC_BEF_TOLERANCE_PT


def _spc_bef_pt(p_elem) -> float | None:
    ppr = p_elem.find(qn("a:pPr"))
    if ppr is None:
        return None
    spc = ppr.find(qn("a:spcBef"))
    if spc is None:
        return None
    pt = spc.find(qn("a:spcPts"))
    if pt is None:
        return None
    return round(int(pt.get("val", 0)) / 100, 4)


def _line_spacing_pt(p_elem) -> float | None:
    ppr = p_elem.find(qn("a:pPr"))
    if ppr is None:
        return None
    ln = ppr.find(qn("a:lnSpc"))
    if ln is None:
        return None
    pt = ln.find(qn("a:spcPts"))
    if pt is None:
        return None
    return round(int(pt.get("val", 0)) / 100, 4)


@dataclass(frozen=True)
class TemplateSpacingSpec:
    """Spacing learned from the reference template sprint block prototype."""

    sprint_line_spc_bef_pt: float | None = None
    sprint_gap_spc_bef_pt: float | None = None
    sprint_gap_line_spacing_pt: float | None = None
    max_blanks_after_current_week: int = 0
    max_blanks_before_subsequent_sprint: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "sprint_line_spc_bef_pt": self.sprint_line_spc_bef_pt,
            "sprint_gap_spc_bef_pt": self.sprint_gap_spc_bef_pt,
            "sprint_gap_line_spacing_pt": self.sprint_gap_line_spacing_pt,
            "max_blanks_after_current_week": self.max_blanks_after_current_week,
            "max_blanks_before_subsequent_sprint": self.max_blanks_before_subsequent_sprint,
        }


def spacing_spec_from_block(block: TemplateBlockSpec) -> TemplateSpacingSpec:
    """Derive spacing limits from ordered template paragraphs."""
    sprint_line_spc: float | None = None
    if block.sprint_line is not None:
        sprint_line_spc = _spc_bef_pt(block.sprint_line.element)

    gap_spc: float | None = None
    gap_line: float | None = None
    if block.sprint_gap is not None:
        gap_spc = _spc_bef_pt(block.sprint_gap.element)
        gap_line = _line_spacing_pt(block.sprint_gap.element)

    blanks_after_current_week = 0
    seen_current_week = False
    for para in block.ordered_paragraphs:
        if para.role == "current_week":
            seen_current_week = True
            blanks_after_current_week = 0
            continue
        if not seen_current_week:
            continue
        if para.role == "blank":
            blanks_after_current_week += 1
            continue
        break

    return TemplateSpacingSpec(
        sprint_line_spc_bef_pt=sprint_line_spc,
        sprint_gap_spc_bef_pt=gap_spc,
        sprint_gap_line_spacing_pt=gap_line,
        max_blanks_after_current_week=blanks_after_current_week,
        max_blanks_before_subsequent_sprint=1 if block.sprint_gap is not None else 0,
    )


def extract_template_spacing_spec(
    template_path: str | Path,
    *,
    prototype_slide_index: int = 2,
) -> TemplateSpacingSpec:
    block = load_block_spec(template_path, prototype_slide_index)
    return spacing_spec_from_block(block)


def detect_hl_spacing_violations(
    hl: dict[str, Any],
    *,
    spacing: TemplateSpacingSpec | None,
    slide_index: int | None = None,
    title: str = "",
) -> list[dict[str, Any]]:
    """Flag extra blank/spacing paragraphs that diverge from the template prototype."""
    if spacing is None:
        return []

    violations: list[dict[str, Any]] = []
    paras = hl.get("paragraphs") or []

    def _add(message: str, detail: dict[str, Any]) -> None:
        violations.append(
            {
                "rule_id": "HL-SPC-03",
                "severity": "major",
                "slide_index": slide_index,
                "title": title,
                "message": message,
                "details": [detail],
            }
        )

    sprint_indices = [
        i for i, para in enumerate(paras) if para.get("role") == "sprint_line"
    ]

    for sprint_idx in sprint_indices[1:]:
        blank_count = 0
        j = sprint_idx - 1
        while j >= 0 and paras[j].get("role") == "blank":
            blank_count += 1
            j -= 1
        if blank_count > spacing.max_blanks_before_subsequent_sprint:
            _add(
                "Extra blank line(s) before the next sprint block "
                f"(template allows {spacing.max_blanks_before_subsequent_sprint})",
                {
                    "issue": "extra_sprint_gap_blanks",
                    "blank_count": blank_count,
                    "expected_max": spacing.max_blanks_before_subsequent_sprint,
                    "paragraph_index": sprint_idx,
                },
            )

    for index, para in enumerate(paras):
        if para.get("role") != "current_week":
            continue
        blank_count = 0
        j = index + 1
        while j < len(paras) and paras[j].get("role") == "blank":
            blank_count += 1
            j += 1
        if blank_count <= spacing.max_blanks_after_current_week:
            continue
        next_role = paras[j].get("role") if j < len(paras) else ""
        if not str(next_role).startswith("category_"):
            continue
        _add(
            "Extra blank line(s) between Current week sprint status and the category header "
            f"(template allows {spacing.max_blanks_after_current_week})",
            {
                "issue": "extra_blanks_after_current_week",
                "blank_count": blank_count,
                "expected_max": spacing.max_blanks_after_current_week,
                "paragraph_index": index,
            },
        )

    for index, para in enumerate(paras):
        if para.get("role") != "sprint_line" or index not in sprint_indices[1:]:
            continue
        spc = para.get("spc_bef_pt")
        expected = spacing.sprint_line_spc_bef_pt
        if (
            spc is not None
            and expected is not None
            and float(spc) > expected + SPC_BEF_TOLERANCE_PT
        ):
            _add(
                f"Sprint line spacing before text ({spc} pt) exceeds template ({expected} pt)",
                {
                    "issue": "sprint_line_spc_bef_high",
                    "spc_bef_pt": spc,
                    "expected_max_spc_bef_pt": expected,
                    "paragraph_index": index,
                },
            )

    return violations
