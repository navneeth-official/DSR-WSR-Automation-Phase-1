"""Template-derived paragraph labels and role classification for validation.

Validation roles and anchor texts are scanned from the reference template .pptx —
no Sustainment-specific English literals are required in the classifier.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.oxml.ns import qn

from app.services.ppt_shape_utils import (
    get_highlights_shape,
    get_key_activities_shape,
    has_highlights_table,
    is_delivery_slide_title,
    paragraph_text,
    slide_title_text,
)

_STORY_BUCKET_ORDER = ("category_completed", "category_released", "category_inprogress")
_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")
_SPRINT_MARKERS = ("stories (total", "stories(total")
_CATEGORY_HEADER_RE = re.compile(
    r"^stories?\s+(completed|released|in[- ]?progress)\b",
    re.IGNORECASE,
)


def normalize_label_text(text: str) -> str:
    """Lowercase, collapse whitespace, strip template placeholders."""
    cleaned = _PLACEHOLDER_RE.sub("", text or "")
    return re.sub(r"\s+", " ", cleaned.replace("\u200b", "").replace("\xa0", " ").strip().lower())


def anchor_needle(text: str, *, max_len: int = 48) -> str:
    """Normalized prefix used for fuzzy category / label matching."""
    norm = normalize_label_text(text)
    if len(norm) <= max_len:
        return norm
    return norm[:max_len].rstrip()


def _para_level(p_elem) -> int:
    p_pr = p_elem.find(qn("a:pPr"))
    if p_pr is None or p_pr.get("lvl") is None:
        return 0
    return int(p_pr.get("lvl"))


def _para_bullet_font(p_elem) -> str:
    p_pr = p_elem.find(qn("a:pPr"))
    if p_pr is None:
        return ""
    bu_font = p_pr.find(qn("a:buFont"))
    return (bu_font.get("typeface") if bu_font is not None else "") or ""


def _looks_like_sprint_line(text: str) -> bool:
    low = normalize_label_text(text)
    if not low:
        return False
    if low.startswith("sprint"):
        return True
    return any(marker in low for marker in _SPRINT_MARKERS)


def _looks_like_category_header_text(text: str) -> bool:
    """Category summary lines such as 'Stories completed this week – N stories'."""
    norm = normalize_label_text(text)
    if not norm:
        return False
    if _CATEGORY_HEADER_RE.search(norm):
        return True
    return norm.startswith("stories ") and "this week" in norm


def _looks_like_story_line(p: dict[str, Any]) -> bool:
    text = (p.get("text") or "").strip()
    if not text:
        return False
    if _looks_like_category_header_text(text):
        return False
    lvl = int(p.get("level") or 0)
    if lvl >= 1:
        return True
    bullet = p.get("bullet")
    if bullet and bullet not in ("•", "none", "unknown"):
        return True
    stripped = text.lstrip()
    return stripped.startswith(("-", "–", "—", "₋", "−"))


def _is_category_level(p: dict[str, Any], category_level: int | None) -> bool:
    text = (p.get("text") or "").strip()
    if _looks_like_category_header_text(text):
        return True
    lvl = int(p.get("level") or 0)
    if category_level is not None and lvl == category_level:
        return True
    # Sustainment templates: Wingdings arrowhead at list level 7+
    if lvl >= 7 and "wingdings" in (p.get("bullet_font") or "").lower():
        return True
    return False


@dataclass
class TemplateLabelSpec:
    """Anchor labels and structural hints extracted from a reference template."""

    template_file: str
    hl_header_text: str = ""
    ka_header_text: str = ""
    current_week_texts: frozenset[str] = frozenset()
    sprint_line_prefixes: frozenset[str] = frozenset()
    category_completed_needles: frozenset[str] = frozenset()
    category_released_needles: frozenset[str] = frozenset()
    category_inprogress_needles: frozenset[str] = frozenset()
    category_header_level: int | None = None
    story_item_level: int | None = None

    def current_week_display(self) -> str:
        if self.current_week_texts:
            return next(iter(sorted(self.current_week_texts, key=len, reverse=True)))
        return "current week status"

    def category_display(self, role: str) -> str:
        needles = {
            "category_completed": self.category_completed_needles,
            "category_released": self.category_released_needles,
            "category_inprogress": self.category_inprogress_needles,
        }.get(role, frozenset())
        if needles:
            return next(iter(sorted(needles, key=len, reverse=True)))
        return role.replace("_", " ")

    def matches_current_week(self, text: str) -> bool:
        norm = normalize_label_text(text)
        if not norm:
            return False
        if norm in self.current_week_texts:
            return True
        return any(norm == anchor or anchor in norm or norm in anchor for anchor in self.current_week_texts)

    def matches_sprint_line(self, text: str) -> bool:
        if _looks_like_sprint_line(text):
            return True
        first = normalize_label_text(text).split(",", 1)[0].strip()
        return first in self.sprint_line_prefixes

    def matches_category(self, text: str, bucket: str) -> bool:
        needles = {
            "category_completed": self.category_completed_needles,
            "category_released": self.category_released_needles,
            "category_inprogress": self.category_inprogress_needles,
        }.get(bucket, frozenset())
        norm = anchor_needle(text)
        if not norm:
            return False
        for needle in needles:
            if needle in norm or norm in needle:
                return True
            prefix = needle.split("–", 1)[0].strip()
            if prefix and len(prefix) >= 12 and norm.startswith(prefix):
                return True
        if not needles and _looks_like_category_header_text(text):
            low = normalize_label_text(text)
            if bucket == "category_completed" and "completed" in low:
                return True
            if bucket == "category_released" and "released" in low:
                return True
            if bucket == "category_inprogress" and "in-progress" in low.replace(" ", ""):
                return True
            if bucket == "category_inprogress" and "in progress" in low:
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_file": self.template_file,
            "hl_header_text": self.hl_header_text,
            "ka_header_text": self.ka_header_text,
            "current_week_texts": sorted(self.current_week_texts),
            "sprint_line_prefixes": sorted(self.sprint_line_prefixes),
            "category_completed_needles": sorted(self.category_completed_needles),
            "category_released_needles": sorted(self.category_released_needles),
            "category_inprogress_needles": sorted(self.category_inprogress_needles),
            "category_header_level": self.category_header_level,
            "story_item_level": self.story_item_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemplateLabelSpec:
        return cls(
            template_file=str(data.get("template_file") or ""),
            hl_header_text=str(data.get("hl_header_text") or ""),
            ka_header_text=str(data.get("ka_header_text") or ""),
            current_week_texts=frozenset(data.get("current_week_texts") or []),
            sprint_line_prefixes=frozenset(data.get("sprint_line_prefixes") or []),
            category_completed_needles=frozenset(data.get("category_completed_needles") or []),
            category_released_needles=frozenset(data.get("category_released_needles") or []),
            category_inprogress_needles=frozenset(data.get("category_inprogress_needles") or []),
            category_header_level=data.get("category_header_level"),
            story_item_level=data.get("story_item_level"),
        )


def classify_paragraph(
    p: dict[str, Any],
    *,
    spec: TemplateLabelSpec | None = None,
    index: int = 0,
    prev_role: str = "",
) -> str:
    """Assign a validation role using template anchors and paragraph structure."""
    text = (p.get("text") or "").strip()
    if not text:
        return "blank"

    if spec and spec.matches_current_week(text):
        return "current_week"
    if spec and spec.matches_sprint_line(text):
        return "sprint_line"
    for bucket in _STORY_BUCKET_ORDER:
        if spec and spec.matches_category(text, bucket):
            return bucket

    lvl = int(p.get("level") or 0)
    category_level = spec.category_header_level if spec else None
    story_level = spec.story_item_level if spec else 1

    if _is_category_level(p, category_level):
        return "category_other"

    if lvl == story_level or (story_level is None and _looks_like_story_line(p)):
        if prev_role.startswith("category_") or prev_role in ("sprint_line", "current_week", "story_item"):
            return "story_item"
        if _looks_like_story_line(p):
            return "story_item"

    if _looks_like_sprint_line(text):
        return "sprint_line"

    if lvl == 0 and prev_role == "sprint_line":
        return "current_week"

    if text.isupper() and lvl == 0 and p.get("bullet") in ("•", None):
        return "project_name"

    return "other"


def classify_paragraphs(
    paras: list[dict[str, Any]],
    spec: TemplateLabelSpec | None = None,
) -> None:
    """Mutate ``paras`` in place, setting ``role`` using a sprint-block state machine."""
    cat_idx = 0
    prev_role = ""
    for i, p in enumerate(paras):
        text = (p.get("text") or "").strip()
        if not text:
            p["role"] = "blank"
            prev_role = "blank"
            continue

        role = classify_paragraph(p, spec=spec, index=i, prev_role=prev_role)

        if role == "sprint_line":
            cat_idx = 0
        elif role.startswith("category_") and role != "category_other":
            cat_idx += 1
        elif role == "category_other":
            role = _STORY_BUCKET_ORDER[min(cat_idx, len(_STORY_BUCKET_ORDER) - 1)]
            cat_idx += 1
        elif role == "other" and _is_category_level(p, spec.category_header_level if spec else None):
            role = _STORY_BUCKET_ORDER[min(cat_idx, len(_STORY_BUCKET_ORDER) - 1)]
            cat_idx += 1
        elif role == "other" and prev_role == "sprint_line" and int(p.get("level") or 0) == 0:
            role = "current_week"
        elif role == "other" and _looks_like_story_line(p):
            role = "story_item"

        p["role"] = role
        prev_role = role


def _collect_hl_paragraphs(cell) -> list[dict[str, Any]]:
    paras: list[dict[str, Any]] = []
    for p_elem in cell.text_frame._txBody.findall(qn("a:p")):
        text = paragraph_text(p_elem).strip()
        paras.append({
            "text": text,
            "level": _para_level(p_elem),
            "bullet_font": _para_bullet_font(p_elem),
        })
    return paras


def _scan_sprint_blocks(paras: list[dict[str, Any]]) -> tuple[set[str], set[str], list[list[str]]]:
    """Return sprint prefixes, current-week texts, and ordered category needles per block."""
    sprint_prefixes: set[str] = set()
    current_week: set[str] = set()
    block_categories: list[list[str]] = []
    in_block = False
    seen_current_week = False
    block_cats: list[str] = []

    for p in paras:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        lvl = int(p.get("level") or 0)

        if _looks_like_sprint_line(text):
            if block_cats:
                block_categories.append(block_cats)
            block_cats = []
            in_block = True
            seen_current_week = False
            sprint_prefixes.add(anchor_needle(text.split(",", 1)[0]))
            continue

        if not in_block:
            continue

        if not seen_current_week and lvl == 0 and not _is_category_level(p, None):
            norm = normalize_label_text(text)
            if norm and not _looks_like_sprint_line(text):
                current_week.add(norm)
                seen_current_week = True
            continue

        if _looks_like_category_header_text(text) or (
            _is_category_level(p, None) and not _looks_like_story_line(p)
        ):
            needle = anchor_needle(text)
            if needle:
                block_cats.append(needle)

    if block_cats:
        block_categories.append(block_cats)

    return sprint_prefixes, current_week, block_categories


def extract_template_label_spec(template_path: str | Path) -> TemplateLabelSpec:
    """Scan delivery slides in the reference template for HL/KA anchor labels."""
    template_path = Path(template_path).resolve()
    if not template_path.is_file():
        raise FileNotFoundError(f"Template not found: {template_path}")

    prs = Presentation(str(template_path))
    sprint_prefixes: set[str] = set()
    current_week: set[str] = set()
    cat_completed: set[str] = set()
    cat_released: set[str] = set()
    cat_inprogress: set[str] = set()
    category_levels: set[int] = set()
    story_levels: set[int] = set()
    hl_header = ""
    ka_header = ""

    for slide in prs.slides:
        title = slide_title_text(slide)
        if not is_delivery_slide_title(title):
            continue
        if not has_highlights_table(slide):
            continue

        hl = get_highlights_shape(slide)
        try:
            header_text = hl.table.cell(0, 0).text.strip()
            if header_text and not hl_header:
                hl_header = header_text
        except (IndexError, AttributeError):
            pass

        cell = hl.table.cell(2, 0)
        paras = _collect_hl_paragraphs(cell)
        sp, cw, blocks = _scan_sprint_blocks(paras)
        sprint_prefixes.update(sp)
        current_week.update(cw)

        for block in blocks:
            for idx, needle in enumerate(block):
                bucket = _STORY_BUCKET_ORDER[min(idx, len(_STORY_BUCKET_ORDER) - 1)]
                if bucket == "category_completed":
                    cat_completed.add(needle)
                elif bucket == "category_released":
                    cat_released.add(needle)
                else:
                    cat_inprogress.add(needle)

        for p in paras:
            text = (p.get("text") or "").strip()
            if not text:
                continue
            lvl = int(p.get("level") or 0)
            if _looks_like_category_header_text(text) or _is_category_level(p, None):
                category_levels.add(lvl)
            elif _looks_like_story_line(p):
                story_levels.add(lvl)

        ka = get_key_activities_shape(slide)
        if ka is not None:
            try:
                header = ka.table.cell(0, 0).text.strip()
                if header and not ka_header:
                    ka_header = header
            except (IndexError, AttributeError):
                pass

    category_level = min(category_levels) if category_levels else 7
    story_level = min(story_levels) if story_levels else 1

    return TemplateLabelSpec(
        template_file=str(template_path),
        hl_header_text=hl_header,
        ka_header_text=ka_header,
        current_week_texts=frozenset(current_week),
        sprint_line_prefixes=frozenset(sprint_prefixes),
        category_completed_needles=frozenset(cat_completed),
        category_released_needles=frozenset(cat_released),
        category_inprogress_needles=frozenset(cat_inprogress),
        category_header_level=category_level,
        story_item_level=story_level,
    )


def load_template_label_spec(path: str | Path) -> TemplateLabelSpec:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return TemplateLabelSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))
    return extract_template_label_spec(path)


def save_template_label_spec(spec: TemplateLabelSpec, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(spec.to_dict(), indent=2), encoding="utf-8")
    return path
