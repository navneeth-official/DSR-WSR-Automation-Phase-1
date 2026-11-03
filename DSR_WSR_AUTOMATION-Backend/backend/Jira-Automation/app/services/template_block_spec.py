"""Read a placeholder Highlights block in the order it appears on the slide."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from pptx.oxml.ns import qn

from app.services.template_placeholders import find_placeholder_tokens, normalize_token_name
from app.services.template_run_substitution import paragraph_plain_text


@dataclass
class ParagraphTemplate:
    role: str
    element: object
    placeholders: frozenset[str] = field(default_factory=frozenset)
    bucket: str | None = None
    text_preview: str = ""


@dataclass
class TemplateBlockSpec:
    sprint_line: ParagraphTemplate | None = None
    current_week: ParagraphTemplate | None = None
    category_headers: dict[str, ParagraphTemplate] = field(default_factory=dict)
    story_bullet: ParagraphTemplate | None = None
    story_bullets: dict[str, ParagraphTemplate] = field(default_factory=dict)
    ordered_paragraphs: list[ParagraphTemplate] = field(default_factory=list)


def _bucket_for(text: str, tokens: list[str]) -> str | None:
    names = {normalize_token_name(token) for token in tokens}
    if "in_progress_count" in names or "in_progress_story_title" in names:
        return "inprogress"
    if "completed_count" in names or "completed_story_title" in names:
        return "completed"
    if "in_review_count" in names or "in_review_story_title" in names:
        return "released"
    low = re.sub(r"\s+", " ", text.lower())
    if "in-progress" in low or "in progress" in low:
        return "inprogress"
    if "released" in low or "in-review" in low or "in review" in low:
        return "released"
    if "completed" in low:
        return "completed"
    return None


def _is_story_token(tokens: list[str]) -> bool:
    names = {normalize_token_name(token) for token in tokens}
    return bool(names & {
        "story_title",
        "completed_story_title",
        "in_review_story_title",
        "in_progress_story_title",
    })


def extract_block_spec_from_cell(cell) -> TemplateBlockSpec:
    spec = TemplateBlockSpec()
    seen_sprint = False
    current_bucket: str | None = None
    for paragraph in cell.text_frame._txBody.findall(qn("a:p")):
        text = paragraph_plain_text(paragraph).strip()
        tokens = find_placeholder_tokens(text)
        low = re.sub(r"\s+", " ", text.lower())
        if not text:
            role = "blank"
            bucket = None
        elif not seen_sprint and ("sprint" in low or "sprint_name" in {normalize_token_name(t) for t in tokens}):
            role = "sprint_line"
            bucket = None
            seen_sprint = True
        elif _is_story_token(tokens):
            role = "story_bullet"
            bucket = _bucket_for(text, tokens) or current_bucket
        elif _bucket_for(text, tokens) and ("stories" in low or "count" in {normalize_token_name(t) for t in tokens}):
            bucket = _bucket_for(text, tokens)
            role = f"category_{bucket}"
            current_bucket = bucket
        elif current_bucket and text:
            bucket = current_bucket
            role = "story_bullet" if current_bucket not in spec.story_bullets else "story_sample"
        elif seen_sprint and spec.current_week is None:
            role = "current_week"
            bucket = None
        else:
            role = "static"
            bucket = None

        item = ParagraphTemplate(
            role=role,
            element=copy.deepcopy(paragraph),
            placeholders=frozenset(tokens),
            bucket=bucket,
            text_preview=text,
        )
        spec.ordered_paragraphs.append(item)
        if role == "sprint_line":
            spec.sprint_line = item
        elif role == "current_week":
            spec.current_week = item
        elif role.startswith("category_") and bucket:
            spec.category_headers[bucket] = item
        elif role == "story_bullet":
            spec.story_bullet = item
            if bucket:
                spec.story_bullets[bucket] = item
    return spec
