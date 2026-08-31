"""Extract Highlights typography reference from a WSR template .pptx."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

from pptx import Presentation

from app.services.ppt_format_extractor import extract_slide
from app.services.ppt_shape_utils import is_delivery_slide_title, slide_title_text

SIZE_TOLERANCE_PT = 0.05
LINE_SPACING_TOLERANCE_PT = 0.5
SPC_BEF_TOLERANCE_PT = 0.15

_THEME_FONT_ALIASES: dict[str, frozenset[str]] = {
    "calibri": frozenset({"+mn-lt", "+mj-lt", "calibri light"}),
    "manrope": frozenset({"+mn-lt", "+mj-lt", "manrope light", "manrope bold"}),
}

_PLACEHOLDER_FONTS = frozenset({"ms gothic", "wingdings", "symbol"})


@dataclass(frozen=True)
class RoleStyleSpec:
    allowed_fonts: frozenset[str] = frozenset()
    size_pt: float | None = None
    bold: bool | None = None
    line_spacing_pt: float | None = None
    max_spc_bef_pt: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_fonts": sorted(self.allowed_fonts),
            "size_pt": self.size_pt,
            "bold": self.bold,
            "line_spacing_pt": self.line_spacing_pt,
            "max_spc_bef_pt": self.max_spc_bef_pt,
        }


@dataclass
class TemplateTypographySpec:
    template_file: str
    header: RoleStyleSpec = field(default_factory=RoleStyleSpec)
    roles: dict[str, RoleStyleSpec] = field(default_factory=dict)

    def role_spec(self, role: str) -> RoleStyleSpec | None:
        if role in self.roles:
            return self.roles[role]
        if role == "story_item":
            return self.roles.get("other") or self.roles.get("story_item")
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_file": self.template_file,
            "header": self.header.to_dict(),
            "roles": {k: v.to_dict() for k, v in sorted(self.roles.items())},
        }


def _norm_font(name: str | None) -> str:
    return (name or "").strip().lower()


def _expand_font_aliases(fonts: set[str]) -> frozenset[str]:
    expanded = {f for f in fonts if f}
    for font in list(expanded):
        for key, aliases in _THEME_FONT_ALIASES.items():
            if key in _norm_font(font):
                expanded.update(aliases)
    return frozenset(expanded)


def _primary_run(para: dict[str, Any]) -> dict[str, Any]:
    runs = para.get("runs") or []
    for run in runs:
        if (run.get("text") or "").strip():
            return run
    return runs[0] if runs else {}


def _collect_role_samples(
    slides: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_role: dict[str, list[dict[str, Any]]] = {}
    header_runs: list[dict[str, Any]] = []
    for slide in slides:
        hl = slide.get("highlights") or {}
        header = hl.get("header_metrics") or {}
        header_runs.extend(header.get("runs") or [])
        for para in hl.get("paragraphs") or []:
            role = str(para.get("role") or "")
            if not role or role == "blank" or not para.get("text"):
                continue
            sample = {
                "font": _primary_run(para).get("font"),
                "size_pt": _primary_run(para).get("size_pt"),
                "bold": _primary_run(para).get("bold"),
                "line_spacing_pt": para.get("line_spacing_pt"),
                "spc_bef_pt": para.get("spc_bef_pt"),
            }
            by_role.setdefault(role, []).append(sample)
    return by_role, header_runs


def _build_role_spec(samples: list[dict[str, Any]]) -> RoleStyleSpec:
    fonts: set[str] = set()
    sizes: list[float] = []
    bold_votes: list[bool] = []
    line_spacings: list[float] = []
    spc_befs: list[float] = []

    for sample in samples:
        font = sample.get("font")
        if font and _norm_font(font) not in _PLACEHOLDER_FONTS:
            fonts.add(str(font))
        size = sample.get("size_pt")
        if size is not None:
            sizes.append(float(size))
        bold = sample.get("bold")
        if bold is not None:
            bold_votes.append(bool(bold))
        line = sample.get("line_spacing_pt")
        if line is not None:
            line_spacings.append(float(line))
        spc = sample.get("spc_bef_pt")
        if spc is not None:
            spc_befs.append(float(spc))

    size_pt = round(float(median(sizes)), 2) if sizes else None
    line_spacing_pt = round(float(median(line_spacings)), 2) if line_spacings else None
    max_spc_bef_pt = round(max(spc_befs) + SPC_BEF_TOLERANCE_PT, 2) if spc_befs else None

    bold: bool | None = None
    if bold_votes:
        bold = Counter(bold_votes).most_common(1)[0][0]

    return RoleStyleSpec(
        allowed_fonts=_expand_font_aliases(fonts),
        size_pt=size_pt,
        bold=bold,
        line_spacing_pt=line_spacing_pt,
        max_spc_bef_pt=max_spc_bef_pt,
    )


def _build_header_spec(header_runs: list[dict[str, Any]]) -> RoleStyleSpec:
    if not header_runs:
        return RoleStyleSpec()
    fonts = {
        str(r["font"])
        for r in header_runs
        if r.get("font") and _norm_font(r.get("font")) not in _PLACEHOLDER_FONTS
    }
    sizes = [float(r["size_pt"]) for r in header_runs if r.get("size_pt") is not None]
    bold_votes = [bool(r["bold"]) for r in header_runs if r.get("bold") is not None]
    return RoleStyleSpec(
        allowed_fonts=_expand_font_aliases(fonts),
        size_pt=round(float(median(sizes)), 2) if sizes else None,
        bold=Counter(bold_votes).most_common(1)[0][0] if bold_votes else None,
    )


def extract_template_typography(template_path: str | Path) -> TemplateTypographySpec:
    """Scan delivery slides in the reference template for HL typography."""
    template_path = Path(template_path).resolve()
    prs = Presentation(str(template_path))
    slide_data: list[dict[str, Any]] = []
    for i, slide in enumerate(prs.slides, start=1):
        title = slide_title_text(slide)
        if not is_delivery_slide_title(title):
            continue
        data = extract_slide(slide, i)
        if data and data.get("highlights"):
            slide_data.append(data)

    if not slide_data:
        raise ValueError(f"No Highlights slides found in template: {template_path}")

    by_role, header_runs = _collect_role_samples(slide_data)
    roles = {role: _build_role_spec(samples) for role, samples in by_role.items()}
    return TemplateTypographySpec(
        template_file=str(template_path),
        header=_build_header_spec(header_runs),
        roles=roles,
    )


def load_template_typography(path: str | Path) -> TemplateTypographySpec:
    """Load a cached typography JSON or extract from .pptx."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        header_raw = data.get("header") or {}
        header = RoleStyleSpec(
            allowed_fonts=frozenset(header_raw.get("allowed_fonts") or []),
            size_pt=header_raw.get("size_pt"),
            bold=header_raw.get("bold"),
            line_spacing_pt=header_raw.get("line_spacing_pt"),
            max_spc_bef_pt=header_raw.get("max_spc_bef_pt"),
        )
        roles = {}
        for role, raw in (data.get("roles") or {}).items():
            roles[role] = RoleStyleSpec(
                allowed_fonts=frozenset(raw.get("allowed_fonts") or []),
                size_pt=raw.get("size_pt"),
                bold=raw.get("bold"),
                line_spacing_pt=raw.get("line_spacing_pt"),
                max_spc_bef_pt=raw.get("max_spc_bef_pt"),
            )
        return TemplateTypographySpec(
            template_file=data.get("template_file", str(path)),
            header=header,
            roles=roles,
        )
    return extract_template_typography(path)


def save_template_typography(spec: TemplateTypographySpec, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    return path
