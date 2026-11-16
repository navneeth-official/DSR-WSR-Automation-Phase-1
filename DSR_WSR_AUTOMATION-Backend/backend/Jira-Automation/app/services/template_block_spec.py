"""Scan template HL cells into ordered block specs for content insertion.

Paragraph roles are detected from **placeholder tokens** (and template order only
as a fallback for generic ``{Count}`` / ``{Story Title}``), not from bullet
indent levels (lvl 7 / Wingdings / etc.).

Spacing (``a:spcBef``, ``a:lnSpc``, blank spacer paragraphs) is preserved by
keeping every paragraph from the first sprint block in **template order** and
replaying that sequence during fill.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from pptx.oxml.ns import qn

from app.services.template_label_spec import _looks_like_sprint_line
from app.services.template_placeholders import (
    bucket_from_token_keys,
    find_placeholder_tokens,
    normalize_token_name,
    STORY_TITLE_TOKEN_KEYS,
)
from app.services.template_run_substitution import paragraph_plain_text

STORY_BUCKET_ORDER = ("completed", "released", "inprogress")

SPRINT_PREFIX_ROLES = frozenset({"sprint_line", "current_week", "static"})


@dataclass
class ParagraphTemplate:
    role: str
    element: Any
    placeholders: frozenset[str] = frozenset()
    bucket: str | None = None
    text_preview: str = ""

    @classmethod
    def from_element(cls, p_elem, role: str, bucket: str | None = None) -> ParagraphTemplate:
        text = paragraph_plain_text(p_elem)
        tokens = frozenset(find_placeholder_tokens(text))
        return cls(
            role=role,
            element=copy.deepcopy(p_elem),
            placeholders=tokens,
            bucket=bucket,
            text_preview=text[:80],
        )


@dataclass
class TemplateBlockSpec:
    """Ordered sprint-block prototype extracted from a reference HL cell."""

    sprint_line: ParagraphTemplate | None = None
    current_week: ParagraphTemplate | None = None
    category_headers: dict[str, ParagraphTemplate] = field(default_factory=dict)
    story_bullet: ParagraphTemplate | None = None
    story_bullets: dict[str, ParagraphTemplate] = field(default_factory=dict)
    sprint_gap: ParagraphTemplate | None = None
    static_paragraphs: list[ParagraphTemplate] = field(default_factory=list)
    ordered_paragraphs: list[ParagraphTemplate] = field(default_factory=list)

    def category_for_bucket(self, bucket: str) -> ParagraphTemplate | None:
        return self.category_headers.get(bucket)

    def story_for_bucket(self, bucket: str) -> ParagraphTemplate | None:
        return self.story_bullets.get(bucket) or self.story_bullet


def _token_keys(text: str) -> set[str]:
    return {normalize_token_name(t) for t in find_placeholder_tokens(text)}


def _is_blank_paragraph(p_elem) -> bool:
    return not paragraph_plain_text(p_elem)


def _is_story_title_paragraph(text: str) -> bool:
    keys = _token_keys(text)
    return bool(keys & STORY_TITLE_TOKEN_KEYS)


def _is_category_header_paragraph(text: str) -> bool:
    keys = _token_keys(text)
    if _is_story_title_paragraph(text):
        return False
    if bucket_from_token_keys(keys) is not None and not keys & STORY_TITLE_TOKEN_KEYS:
        return True
    return "count" in keys


def _is_sprint_line_paragraph(text: str) -> bool:
    keys = _token_keys(text)
    if "sprint_name" in keys or "status" in keys and "sprint" in text.lower():
        return True
    return _looks_like_sprint_line(text)


def _split_first_sprint_block(
    paras_xml: list,
) -> list[tuple[Any, str]]:
    """Return paragraphs belonging to the first sprint block (prototype), in order."""
    block: list[tuple[Any, str]] = []
    seen_sprint = False
    started = False

    for p_elem in paras_xml:
        text = paragraph_plain_text(p_elem)
        is_blank = _is_blank_paragraph(p_elem)

        if _is_sprint_line_paragraph(text):
            if seen_sprint and block:
                break
            seen_sprint = True
            started = True
            block.append((p_elem, text))
            continue

        if not started:
            if is_blank:
                continue
            started = True

        if started:
            block.append((p_elem, text))

    if not block:
        return [(p, paragraph_plain_text(p)) for p in paras_xml if not _is_blank_paragraph(p)]

    return block


def _classify_paragraph(
    text: str,
    *,
    cat_idx: int,
    pending_bucket: str | None,
) -> tuple[str, str | None]:
    """Return (role, bucket) for one non-blank paragraph."""
    if _is_sprint_line_paragraph(text):
        return "sprint_line", None

    if _is_story_title_paragraph(text):
        keys = _token_keys(text)
        bucket = bucket_from_token_keys(keys) or pending_bucket
        return "story_bullet", bucket

    if _is_category_header_paragraph(text):
        keys = _token_keys(text)
        bucket = bucket_from_token_keys(keys)
        if bucket is None:
            bucket = STORY_BUCKET_ORDER[min(cat_idx, len(STORY_BUCKET_ORDER) - 1)]
        return f"category_{bucket}", bucket

    if not find_placeholder_tokens(text):
        return "current_week", None

    return "static", None


def extract_block_spec_from_cell(cell, label_spec=None) -> TemplateBlockSpec:
    """Build a TemplateBlockSpec from one HL content table cell."""
    del label_spec  # roles no longer depend on TemplateLabelSpec levels

    paras_xml = cell.text_frame._txBody.findall(qn("a:p"))
    block = _split_first_sprint_block(paras_xml)

    spec = TemplateBlockSpec()
    cat_idx = 0
    pending_bucket: str | None = None
    current_week_assigned = False

    for p_elem, text in block:
        if not text:
            blank = ParagraphTemplate.from_element(p_elem, "blank")
            spec.ordered_paragraphs.append(blank)
            if spec.sprint_line is not None and spec.sprint_gap is None:
                spec.sprint_gap = blank
            continue

        role, bucket = _classify_paragraph(
            text, cat_idx=cat_idx, pending_bucket=pending_bucket
        )

        if role == "sprint_line":
            tmpl = ParagraphTemplate.from_element(p_elem, role)
            spec.sprint_line = tmpl
            spec.ordered_paragraphs.append(tmpl)
            pending_bucket = None
            continue

        if role == "story_bullet":
            tmpl = ParagraphTemplate.from_element(p_elem, role, bucket=bucket)
            if bucket:
                spec.story_bullets.setdefault(bucket, tmpl)
                pending_bucket = None
            elif spec.story_bullet is None:
                spec.story_bullet = tmpl
            spec.ordered_paragraphs.append(tmpl)
            continue

        if role.startswith("category_"):
            bucket = role.replace("category_", "")
            cat_idx += 1
            if bucket not in spec.category_headers:
                tmpl = ParagraphTemplate.from_element(p_elem, role, bucket=bucket)
                spec.category_headers[bucket] = tmpl
            else:
                tmpl = ParagraphTemplate.from_element(p_elem, role, bucket=bucket)
            spec.ordered_paragraphs.append(tmpl)
            pending_bucket = bucket
            continue

        if role == "current_week" and not current_week_assigned and spec.sprint_line is not None:
            tmpl = ParagraphTemplate.from_element(p_elem, "current_week")
            spec.current_week = tmpl
            spec.ordered_paragraphs.append(tmpl)
            current_week_assigned = True
            continue

        tmpl = ParagraphTemplate.from_element(p_elem, "static")
        spec.static_paragraphs.append(tmpl)
        spec.ordered_paragraphs.append(tmpl)

    return spec


def extract_block_spec_for_slide(slide, label_spec=None) -> TemplateBlockSpec:
    from app.services.ppt_shape_utils import get_highlights_shape

    hl = get_highlights_shape(slide)
    cell = hl.table.cell(2, 0)
    return extract_block_spec_from_cell(cell, label_spec)


def load_block_spec(template_path, slide_index: int, label_spec=None) -> TemplateBlockSpec:
    from pptx import Presentation

    prs = Presentation(str(template_path))
    slide = prs.slides[slide_index]
    from app.services.template_label_spec import extract_template_label_spec

    labels = label_spec or extract_template_label_spec(template_path)
    return extract_block_spec_for_slide(slide, labels)
