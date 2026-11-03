"""Fill a placeholder Highlights block by substituting tokens and repeating story rows."""

from __future__ import annotations

import copy
import logging
import re

from pptx.oxml.ns import qn

from app.services.template_block_spec import ParagraphTemplate, TemplateBlockSpec, extract_block_spec_from_cell
from app.services.template_placeholders import PlaceholderContext, find_placeholder_tokens
from app.services.template_run_substitution import (
    _run_text,
    _set_run_text,
    paragraph_plain_text,
    substitute_placeholders_in_paragraph,
)
from app.wsr_engine.placeholder_locator import highlights_content_cell

logger = logging.getLogger(__name__)

# Stable path labels for generate / job logs
PIPELINE_PLACEHOLDER_FILL = "PLACEHOLDER_FILL"
PIPELINE_REBUILD_SECTION_TEMPLATES = "REBUILD_SECTION_TEMPLATES"
PIPELINE_KA_PLACEHOLDER_STORY_LIST = "KA_PLACEHOLDER_STORY_LIST"
PIPELINE_KA_REPLACE_BULLET_BLOCK = "KA_REPLACE_BULLET_BLOCK"


def _bucket_items(section: dict, bucket: str) -> list[str]:
    aliases = {
        "completed": ("completed", "completed_items"),
        "released": ("released", "released_items"),
        "inprogress": ("inprogress", "inprogress_items"),
    }
    for key in aliases[bucket]:
        value = section.get(key)
        if value:
            return [str(item) for item in value]
    return []


def _apply_story_text(paragraph, title: str, ctx: PlaceholderContext) -> None:
    ctx.extra["story_title"] = title
    if find_placeholder_tokens(paragraph_plain_text(paragraph)):
        substitute_placeholders_in_paragraph(paragraph, ctx)
        return
    runs = [run for run in paragraph.findall(qn("a:r")) if run.findall(qn("a:t"))]
    if not runs:
        return
    target = runs[-1]
    old = _run_text(target)
    _set_run_text(target, f"\t{title}" if "\t" in old else title)


def _emit(paragraph: ParagraphTemplate, ctx: PlaceholderContext, story_title: str | None = None):
    clone = copy.deepcopy(paragraph.element)
    if story_title is not None:
        _apply_story_text(clone, story_title, ctx)
    else:
        substitute_placeholders_in_paragraph(clone, ctx)
    return clone


def _groups(spec: TemplateBlockSpec) -> list[list[ParagraphTemplate]]:
    if spec.ordered_paragraphs:
        return [spec.ordered_paragraphs]
    rows: list[ParagraphTemplate] = []
    if spec.sprint_line is not None:
        rows.append(spec.sprint_line)
    if spec.current_week is not None:
        rows.append(spec.current_week)
    for bucket, header in spec.category_headers.items():
        rows.append(header)
        bullet = spec.story_bullets.get(bucket) or spec.story_bullet
        if bullet is not None:
            rows.append(ParagraphTemplate(
                role="story_bullet",
                element=bullet.element,
                placeholders=bullet.placeholders,
                bucket=bucket,
                text_preview=bullet.text_preview,
            ))
    return [rows]


def _kept_rows(rows: list[ParagraphTemplate], section: dict) -> list[tuple[ParagraphTemplate, str | None]]:
    bucket_of: dict[int, str | None] = {}
    current: str | None = None
    for index, row in enumerate(rows):
        if row.role.startswith("category_") or row.role in {"story_bullet", "story_sample"}:
            current = row.bucket
        bucket_of[index] = current if row.role != "blank" else None
    for index, row in enumerate(rows):
        if row.role != "blank":
            continue
        previous = next((rows[pos] for pos in range(index - 1, -1, -1) if rows[pos].role != "blank"), None)
        following = next((rows[pos] for pos in range(index + 1, len(rows)) if rows[pos].role != "blank"), None)
        owner = None
        if previous is not None and (
            previous.role.startswith("category_") or previous.role in {"story_bullet", "story_sample"}
        ):
            owner = previous.bucket
        elif following is not None and following.role.startswith("category_"):
            owner = following.bucket
        bucket_of[index] = owner

    kept: list[tuple[ParagraphTemplate, str | None]] = []
    for index, row in enumerate(rows):
        bucket = bucket_of[index]
        if row.role == "story_sample":
            continue
        if bucket and not _bucket_items(section, bucket):
            continue
        if row.role == "story_bullet" and bucket:
            items = _bucket_items(section, bucket)
            kept.extend((row, item) for item in items)
            continue
        kept.append((row, None))
    return kept


def fill_highlights_cell(cell, block_spec: TemplateBlockSpec, sections: list[dict], track_name: str = "") -> None:
    body = cell.text_frame._txBody
    for paragraph in list(body.findall(qn("a:p"))):
        body.remove(paragraph)
    rows = _groups(block_spec)[0]
    for section in sections:
        for row, story in _kept_rows(rows, section):
            ctx = PlaceholderContext.from_section(section, bucket=row.bucket, track_name=track_name)
            body.append(_emit(row, ctx, story))
    if not body.findall(qn("a:p")):
        from pptx.oxml import parse_xml

        body.append(parse_xml('<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'))


def fill_placeholder_story_list(tx_body, items: list[str]) -> None:
    """Repeat the placeholder bullet once per story, dropping the token when empty."""
    paragraphs = tx_body.findall(qn("a:p"))
    template = next(
        (p for p in paragraphs if find_placeholder_tokens(paragraph_plain_text(p))),
        paragraphs[0] if paragraphs else None,
    )
    for paragraph in list(paragraphs):
        tx_body.remove(paragraph)
    if template is None:
        return
    titles = [item.strip() for item in items if item and item.strip()]
    if not titles:
        clone = copy.deepcopy(template)
        for run in clone.findall(qn("a:r")):
            _set_run_text(run, "")
        tx_body.append(clone)
        return
    for title in titles:
        clone = copy.deepcopy(template)
        _apply_story_text(clone, title, PlaceholderContext())
        tx_body.append(clone)


def cell_has_placeholders(cell) -> bool:
    text = "".join(paragraph_plain_text(p) for p in cell.text_frame._txBody.findall(qn("a:p")))
    return bool(re.search(r"\{[^{}]+\}", text))


def fill_slide_highlights_if_placeholder(slide, sections: list[dict], track_name: str = "") -> bool:
    """Substitute placeholders when this slide uses the placeholder template.

    Returns True if PLACEHOLDER_FILL ran; False means caller should use
    REBUILD_SECTION_TEMPLATES.
    """
    label = track_name or "(unnamed)"
    try:
        cell = highlights_content_cell(slide)
    except ValueError:
        logger.info(
            "HL pipeline [%s]: skip %s — Highlights content cell not found",
            label,
            PIPELINE_PLACEHOLDER_FILL,
        )
        return False
    if not cell_has_placeholders(cell):
        logger.info(
            "HL pipeline [%s]: skip %s — no {…} tokens in Highlights cell",
            label,
            PIPELINE_PLACEHOLDER_FILL,
        )
        return False
    fill_highlights_cell(cell, extract_block_spec_from_cell(cell), sections, track_name=track_name)
    return True
