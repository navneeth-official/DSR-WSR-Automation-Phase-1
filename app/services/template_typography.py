"""Extract Highlights typography reference from a WSR template .pptx."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

from pptx import Presentation

from app.constants.ppt_bullets import CategoryBulletSpec
from app.services.ppt_format_extractor import extract_slide
from app.services.ppt_shape_utils import is_delivery_slide_title, slide_title_text
from app.services.template_label_spec import TemplateLabelSpec, extract_template_label_spec

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
    allowed_sizes_pt: frozenset[float] = frozenset()
    bold: bool | None = None
    italic: bool | None = None
    allowed_colors: frozenset[str] = frozenset()
    line_spacing_pt: float | None = None
    max_spc_bef_pt: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_fonts": sorted(self.allowed_fonts),
            "size_pt": self.size_pt,
            "allowed_sizes_pt": sorted(self.allowed_sizes_pt),
            "bold": self.bold,
            "italic": self.italic,
            "allowed_colors": sorted(self.allowed_colors),
            "line_spacing_pt": self.line_spacing_pt,
            "max_spc_bef_pt": self.max_spc_bef_pt,
        }


def allowed_sizes_for_spec(spec: RoleStyleSpec) -> frozenset[float]:
    """All template-learned point sizes for a role (every run, not just median)."""
    if spec.allowed_sizes_pt:
        return spec.allowed_sizes_pt
    if spec.size_pt is not None:
        return frozenset({float(spec.size_pt)})
    return frozenset()


def size_matches_spec(actual: float | None, spec: RoleStyleSpec) -> bool:
    if actual is None:
        return True
    allowed = allowed_sizes_for_spec(spec)
    if not allowed:
        return True
    return any(abs(float(actual) - size) <= SIZE_TOLERANCE_PT for size in allowed)


@dataclass
class TemplateTypographySpec:
    template_file: str
    header: RoleStyleSpec = field(default_factory=RoleStyleSpec)
    roles: dict[str, RoleStyleSpec] = field(default_factory=dict)
    category_bullet: CategoryBulletSpec | None = None

    def role_spec(self, role: str) -> RoleStyleSpec | None:
        if role in self.roles:
            return self.roles[role]
        if role == "story_item":
            return self.roles.get("other") or self.roles.get("story_item")
        return None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "template_file": self.template_file,
            "header": self.header.to_dict(),
            "roles": {k: v.to_dict() for k, v in sorted(self.roles.items())},
        }
        if self.category_bullet is not None:
            payload["category_bullet"] = {
                "levels": sorted(self.category_bullet.levels),
                "bullet_chars": sorted(self.category_bullet.bullet_chars),
                "bullet_fonts": sorted(self.category_bullet.bullet_fonts),
            }
        return payload


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
            runs = para.get("runs") or []
            if not runs:
                runs = [_primary_run(para)]
            for run in runs:
                if not (run.get("text") or "").strip() and len(runs) > 1:
                    continue
                sample = {
                    "font": run.get("font"),
                    "size_pt": run.get("size_pt"),
                    "bold": run.get("bold"),
                    "italic": run.get("italic"),
                    "color": run.get("color"),
                    "line_spacing_pt": para.get("line_spacing_pt"),
                    "spc_bef_pt": para.get("spc_bef_pt"),
                }
                by_role.setdefault(role, []).append(sample)
    return by_role, header_runs


_STORY_ROLES = frozenset({"story_item", "other"})


def _build_role_spec(
    samples: list[dict[str, Any]],
    *,
    prefer_regular: bool = False,
) -> RoleStyleSpec:
    fonts: set[str] = set()
    colors: set[str] = set()
    sizes: list[float] = []
    bold_votes: list[bool] = []
    italic_votes: list[bool] = []
    line_spacings: list[float] = []
    spc_befs: list[float] = []

    for sample in samples:
        font = sample.get("font")
        if font and _norm_font(font) not in _PLACEHOLDER_FONTS:
            fonts.add(str(font))
        color = sample.get("color")
        if color:
            colors.add(str(color).upper() if not str(color).startswith("scheme:") else str(color).lower())
        size = sample.get("size_pt")
        if size is not None:
            sizes.append(float(size))
        bold = sample.get("bold")
        if bold is not None:
            bold_votes.append(bool(bold))
        italic = sample.get("italic")
        if italic is not None:
            italic_votes.append(bool(italic))
        line = sample.get("line_spacing_pt")
        if line is not None:
            line_spacings.append(float(line))
        spc = sample.get("spc_bef_pt")
        if spc is not None:
            spc_befs.append(float(spc))

    size_pt = round(float(median(sizes)), 2) if sizes else None
    allowed_sizes_pt = frozenset(round(float(s), 2) for s in sizes)
    line_spacing_pt = round(float(median(line_spacings)), 2) if line_spacings else None
    max_spc_bef_pt = round(max(spc_befs) + SPC_BEF_TOLERANCE_PT, 2) if spc_befs else None

    bold: bool | None = None
    if prefer_regular:
        bold = False
    elif bold_votes:
        bold = Counter(bold_votes).most_common(1)[0][0]

    italic: bool | None = None
    if italic_votes:
        italic = Counter(italic_votes).most_common(1)[0][0]

    return RoleStyleSpec(
        allowed_fonts=_expand_font_aliases(fonts),
        size_pt=size_pt,
        allowed_sizes_pt=allowed_sizes_pt,
        bold=bold,
        italic=italic,
        allowed_colors=frozenset(colors),
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
    italic_votes = [bool(r["italic"]) for r in header_runs if r.get("italic") is not None]
    colors = {
        str(r["color"]).upper() if not str(r["color"]).startswith("scheme:") else str(r["color"]).lower()
        for r in header_runs
        if r.get("color")
    }
    return RoleStyleSpec(
        allowed_fonts=_expand_font_aliases(fonts),
        size_pt=round(float(median(sizes)), 2) if sizes else None,
        allowed_sizes_pt=frozenset(round(float(s), 2) for s in sizes),
        bold=Counter(bold_votes).most_common(1)[0][0] if bold_votes else None,
        italic=Counter(italic_votes).most_common(1)[0][0] if italic_votes else None,
        allowed_colors=frozenset(colors),
    )


def _extract_category_bullet_spec(
    slides: list[dict[str, Any]],
) -> CategoryBulletSpec | None:
    levels: set[int] = set()
    chars: set[str] = set()
    fonts: set[str] = set()
    for slide in slides:
        for para in (slide.get("highlights") or {}).get("paragraphs") or []:
            role = str(para.get("role") or "")
            if not role.startswith("category_") or not para.get("text"):
                continue
            level = para.get("level")
            bullet = para.get("bullet")
            font = (para.get("bullet_font") or "").strip()
            if level is None or bullet is None:
                continue
            levels.add(int(level))
            chars.add(str(bullet))
            if font:
                fonts.add(font)
    if not levels or not chars:
        return None
    return CategoryBulletSpec(
        levels=frozenset(levels),
        bullet_chars=frozenset(chars),
        bullet_fonts=frozenset(fonts),
    )


def extract_template_typography(
    template_path: str | Path,
    *,
    label_spec: TemplateLabelSpec | None = None,
) -> TemplateTypographySpec:
    """Scan delivery slides in the reference template for HL typography."""
    template_path = Path(template_path).resolve()
    resolved_labels = label_spec or extract_template_label_spec(template_path)
    prs = Presentation(str(template_path))
    slide_data: list[dict[str, Any]] = []
    for i, slide in enumerate(prs.slides, start=1):
        title = slide_title_text(slide)
        if not is_delivery_slide_title(title):
            continue
        data = extract_slide(slide, i, label_spec=resolved_labels)
        if data and data.get("highlights"):
            slide_data.append(data)

    if not slide_data:
        raise ValueError(f"No Highlights slides found in template: {template_path}")

    by_role, header_runs = _collect_role_samples(slide_data)
    roles = {
        role: _build_role_spec(samples, prefer_regular=role in _STORY_ROLES)
        for role, samples in by_role.items()
    }
    return TemplateTypographySpec(
        template_file=str(template_path),
        header=_build_header_spec(header_runs),
        roles=roles,
        category_bullet=_extract_category_bullet_spec(slide_data),
    )


def load_template_typography(
    path: str | Path,
    *,
    label_spec: TemplateLabelSpec | None = None,
) -> TemplateTypographySpec:
    """Load a cached typography JSON or extract from .pptx."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        header_raw = data.get("header") or {}
        header = RoleStyleSpec(
            allowed_fonts=frozenset(header_raw.get("allowed_fonts") or []),
            size_pt=header_raw.get("size_pt"),
            allowed_sizes_pt=frozenset(
                float(v) for v in (header_raw.get("allowed_sizes_pt") or [])
            ),
            bold=header_raw.get("bold"),
            italic=header_raw.get("italic"),
            allowed_colors=frozenset(header_raw.get("allowed_colors") or []),
            line_spacing_pt=header_raw.get("line_spacing_pt"),
            max_spc_bef_pt=header_raw.get("max_spc_bef_pt"),
        )
        roles = {}
        for role, raw in (data.get("roles") or {}).items():
            roles[role] = RoleStyleSpec(
                allowed_fonts=frozenset(raw.get("allowed_fonts") or []),
                size_pt=raw.get("size_pt"),
                allowed_sizes_pt=frozenset(
                    float(v) for v in (raw.get("allowed_sizes_pt") or [])
                ),
                bold=raw.get("bold"),
                italic=raw.get("italic"),
                allowed_colors=frozenset(raw.get("allowed_colors") or []),
                line_spacing_pt=raw.get("line_spacing_pt"),
                max_spc_bef_pt=raw.get("max_spc_bef_pt"),
            )
        category_bullet = None
        raw_bullet = data.get("category_bullet") or {}
        if raw_bullet.get("levels") and raw_bullet.get("bullet_chars"):
            category_bullet = CategoryBulletSpec(
                levels=frozenset(int(v) for v in raw_bullet["levels"]),
                bullet_chars=frozenset(str(v) for v in raw_bullet["bullet_chars"]),
                bullet_fonts=frozenset(str(v) for v in raw_bullet.get("bullet_fonts") or []),
            )
        return TemplateTypographySpec(
            template_file=data.get("template_file", str(path)),
            header=header,
            roles=roles,
            category_bullet=category_bullet,
        )
    return extract_template_typography(path, label_spec=label_spec)


def save_template_typography(spec: TemplateTypographySpec, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    return path
