"""Template-driven Highlights / title / KA content insertion."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from pptx.oxml.ns import qn

from app.services.ppt_hl_bullets import set_story_line_text
from app.services.ppt_ka_bullets import replace_ka_bullet_block
from app.services.ppt_shape_utils import find_title_shape, paragraph_text
from app.services.template_block_spec import (
    SPRINT_PREFIX_ROLES,
    STORY_BUCKET_ORDER,
    ParagraphTemplate,
    TemplateBlockSpec,
)
from app.services.template_placeholders import PlaceholderContext
from app.services.template_placeholders import find_placeholder_tokens
from app.services.template_run_substitution import (
    clone_paragraph_with_substitution,
    normalize_sprint_line_bold_runs,
    normalize_story_line_runs,
    paragraph_plain_text,
    substitute_placeholders_in_paragraph,
    substitute_placeholders_in_shape_text_frame,
)

_BUCKET_ITEMS = {
    "completed": ("completed", "completed_items"),
    "released": ("released", "released_items"),
    "inprogress": ("inprogress", "inprogress_items"),
}


def _section_items(section: Any, bucket: str) -> list[str]:
    if hasattr(section, bucket):
        raw = getattr(section, bucket)
        if raw:
            return list(raw)
    if isinstance(section, dict):
        for key in _BUCKET_ITEMS[bucket]:
            raw = section.get(key)
            if raw:
                return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _section_get(section: Any, key: str, default=None):
    if hasattr(section, key):
        return getattr(section, key)
    if isinstance(section, dict):
        return section.get(key, default)
    return default


def _append_paragraph(tx_body, p_elem) -> None:
    tx_body.append(p_elem)


def _clone_static_paragraph(template) -> object | None:
    if template is None:
        return None
    return copy.deepcopy(template.element)


def _append_story_bullets(tx_body, story_template, items: list[str]) -> None:
    if not items or story_template is None:
        return
    for text in items:
        bullet = copy.deepcopy(story_template.element)
        if find_placeholder_tokens(paragraph_plain_text(bullet)):
            ctx = PlaceholderContext(extra={"story_title": text})
            substitute_placeholders_in_paragraph(bullet, ctx)
        else:
            set_story_line_text(bullet, text)
        normalize_story_line_runs(bullet)
        _append_paragraph(tx_body, bullet)


def _bucket_for_paragraph(para: ParagraphTemplate) -> str | None:
    if para.bucket:
        return para.bucket
    if para.role.startswith("category_"):
        return para.role.replace("category_", "", 1)
    return None


def _section_bucket_items(section: Any) -> dict[str, list[str]]:
    return {bucket: _section_items(section, bucket) for bucket in STORY_BUCKET_ORDER}


def _should_emit_paragraph(
    para: ParagraphTemplate,
    *,
    continued: bool,
    omit: set[str],
    bucket_items: dict[str, list[str]],
) -> bool:
    role = para.role
    bucket = _bucket_for_paragraph(para)

    if role in SPRINT_PREFIX_ROLES:
        return not continued

    if role == "blank":
        return True

    if role.startswith("category_"):
        if not bucket:
            return False
        if bucket in omit:
            return False
        return bool(bucket_items.get(bucket))

    if role == "story_bullet":
        if not bucket:
            return bool(any(bucket_items.values()))
        if bucket in omit:
            return False
        return bool(bucket_items.get(bucket))

    return True


def _emit_paragraph(
    tx_body,
    para: ParagraphTemplate,
    *,
    section: Any,
    track_name: str,
    bucket_items: dict[str, list[str]],
) -> None:
    role = para.role
    bucket = _bucket_for_paragraph(para)

    if role == "blank":
        _append_paragraph(tx_body, copy.deepcopy(para.element))
        return

    if role == "sprint_line":
        ctx = PlaceholderContext.from_section(section, track_name=track_name)
        sprint_p = clone_paragraph_with_substitution(para.element, ctx)
        normalize_sprint_line_bold_runs(sprint_p)
        _append_paragraph(tx_body, sprint_p)
        return

    if role.startswith("category_"):
        ctx = PlaceholderContext.from_section(
            section, track_name=track_name, bucket=bucket
        )
        _append_paragraph(
            tx_body,
            clone_paragraph_with_substitution(para.element, ctx),
        )
        return

    if role == "story_bullet":
        items = bucket_items.get(bucket or "", [])
        for text in items:
            bullet = copy.deepcopy(para.element)
            if find_placeholder_tokens(paragraph_plain_text(bullet)):
                ctx = PlaceholderContext(extra={"story_title": text})
                substitute_placeholders_in_paragraph(bullet, ctx)
            else:
                set_story_line_text(bullet, text)
            normalize_story_line_runs(bullet)
            _append_paragraph(tx_body, bullet)
        return

    _append_paragraph(tx_body, copy.deepcopy(para.element))


def _fill_section_ordered(
    tx_body,
    block_spec: TemplateBlockSpec,
    section: Any,
    *,
    track_name: str,
) -> None:
    """Replay template paragraphs in order, preserving spacing XML."""
    continued = bool(_section_get(section, "continued_section", False))
    omit = set(_section_get(section, "omit_category_headers", []) or [])
    bucket_items = _section_bucket_items(section)

    pending_blanks: list[ParagraphTemplate] = []
    skip_bucket: str | None = None

    for para in block_spec.ordered_paragraphs:
        bucket = _bucket_for_paragraph(para)

        if skip_bucket:
            if para.role == "blank":
                continue
            if bucket == skip_bucket and para.role == "story_bullet":
                continue
            skip_bucket = None

        if para.role == "blank":
            pending_blanks.append(para)
            continue

        if not _should_emit_paragraph(
            para,
            continued=continued,
            omit=omit,
            bucket_items=bucket_items,
        ):
            pending_blanks.clear()
            if para.role.startswith("category_") and bucket and not bucket_items.get(bucket):
                skip_bucket = bucket
            continue

        for blank in pending_blanks:
            _emit_paragraph(
                tx_body,
                blank,
                section=section,
                track_name=track_name,
                bucket_items=bucket_items,
            )
        pending_blanks.clear()

        _emit_paragraph(
            tx_body,
            para,
            section=section,
            track_name=track_name,
            bucket_items=bucket_items,
        )


def _fill_section_legacy(
    tx_body,
    block_spec: TemplateBlockSpec,
    section: Any,
    *,
    track_name: str,
    continued: bool,
    omit: set[str],
) -> None:
    """Fallback when ordered_paragraphs is empty (tests / hand-built specs)."""
    if not continued:
        if block_spec.sprint_line is not None:
            ctx = PlaceholderContext.from_section(section, track_name=track_name)
            sprint_p = clone_paragraph_with_substitution(
                block_spec.sprint_line.element, ctx
            )
            normalize_sprint_line_bold_runs(sprint_p)
            _append_paragraph(tx_body, sprint_p)

        if block_spec.current_week is not None:
            cw = _clone_static_paragraph(block_spec.current_week)
            if cw is not None:
                _append_paragraph(tx_body, cw)

        for static in block_spec.static_paragraphs:
            if static.role == "current_week":
                continue
            sp = _clone_static_paragraph(static)
            if sp is not None:
                _append_paragraph(tx_body, sp)

    for bucket in STORY_BUCKET_ORDER:
        if bucket in omit:
            continue
        items = _section_items(section, bucket)
        if not items:
            continue

        header = block_spec.category_for_bucket(bucket)
        if header is not None:
            ctx = PlaceholderContext.from_section(
                section, track_name=track_name, bucket=bucket
            )
            hdr_p = clone_paragraph_with_substitution(header.element, ctx)
            _append_paragraph(tx_body, hdr_p)

        story_tpl = block_spec.story_for_bucket(bucket)
        _append_story_bullets(tx_body, story_tpl, items)


def fill_highlights_cell(
    hl_cell,
    block_spec: TemplateBlockSpec,
    sections: list[Any],
    *,
    track_name: str = "",
) -> None:
    """
    Rebuild HL content from template block spec + section data.

    When ``ordered_paragraphs`` is populated, replays the template sequence
    verbatim (including blank spacer paragraphs and ``a:pPr`` spacing).
    Placeholders are substituted at run level; empty story buckets are omitted.
    """
    hl_tx_body = hl_cell.text_frame._txBody
    for p in list(hl_tx_body.findall(qn("a:p"))):
        hl_tx_body.remove(p)

    if not sections:
        return

    use_ordered = bool(block_spec.ordered_paragraphs)

    for si, section in enumerate(sections):
        if si > 0 and block_spec.sprint_gap is not None:
            gap = _clone_static_paragraph(block_spec.sprint_gap)
            if gap is not None:
                _append_paragraph(hl_tx_body, gap)

        if use_ordered:
            _fill_section_ordered(
                hl_tx_body,
                block_spec,
                section,
                track_name=track_name,
            )
        else:
            continued = bool(_section_get(section, "continued_section", False))
            omit = set(_section_get(section, "omit_category_headers", []) or [])
            _fill_section_legacy(
                hl_tx_body,
                block_spec,
                section,
                track_name=track_name,
                continued=continued,
                omit=omit,
            )

    _strip_trailing_empty_paragraphs(hl_tx_body)


def fill_highlights_contd_cell(
    hl_cell,
    block_spec: TemplateBlockSpec,
    sections: list[Any],
    *,
    track_name: str = "",
) -> None:
    """Continuation slides: bucket blocks only (no sprint/current_week unless not continued)."""
    fill_highlights_cell(hl_cell, block_spec, sections, track_name=track_name)


def substitute_title_placeholders(slide, track_name: str, ref_title_shape=None) -> None:
    """Replace {Track Name} (and other tokens) in the slide title shape."""
    try:
        title_shape = find_title_shape(slide)
    except RuntimeError:
        return
    ctx = PlaceholderContext(track_name=track_name)
    substitute_placeholders_in_shape_text_frame(title_shape, ctx)


def set_delivery_title_from_template(
    slide,
    track_name: str,
    ref_title_shape,
    *,
    title_paragraph_templates: list | None = None,
) -> None:
    """
    Copy title shape from reference when missing, then substitute placeholders
    in the template title text (preserves static prefix/suffix from template).

    ``title_paragraph_templates`` should be a deep copy of the prototype title
    paragraphs *before* any substitution so each cloned slide gets a fresh
    ``{Track Name}`` (or other tokens) rather than the first project's values.
    """
    try:
        title_shape = find_title_shape(slide)
    except RuntimeError:
        new_el = copy.deepcopy(ref_title_shape.element)
        slide.shapes._spTree.insert_element_before(new_el, "p:extLst")
        title_shape = find_title_shape(slide)

    if title_paragraph_templates:
        title_shape.text_frame.clear()
        for p_elem in title_paragraph_templates:
            title_shape.text_frame._txBody.append(copy.deepcopy(p_elem))
    elif ref_title_shape is not None and title_shape.element is not ref_title_shape.element:
        title_shape.text_frame.clear()
        for src_p in ref_title_shape.text_frame.paragraphs:
            title_shape.text_frame._txBody.append(copy.deepcopy(src_p._p))

    substitute_title_placeholders(slide, track_name)


def fill_ka_items(ka_shape, items: list[str]) -> None:
    """Fill KA content cell bullets from template-cloned paragraphs."""
    from app.constants.ppt_mapping import KA_PLACEHOLDER_ROWS

    resolved = [str(i).strip() for i in items if str(i).strip()]
    if not resolved:
        resolved = [""] * max(KA_PLACEHOLDER_ROWS, 1)

    tx_body = ka_shape.table.cell(1, 0).text_frame._txBody
    all_p = tx_body.findall(qn("a:p"))
    if not all_p:
        return
    replace_ka_bullet_block(tx_body, 0, len(all_p) - 1, resolved)


def _strip_trailing_empty_paragraphs(tx_body) -> None:
    all_p = tx_body.findall(qn("a:p"))
    while len(all_p) > 1:
        if paragraph_text(all_p[-1]).strip():
            break
        tx_body.remove(all_p[-1])
        all_p = tx_body.findall(qn("a:p"))


def section_to_payload(section: Any) -> dict[str, Any]:
    """Normalize SprintSection or dict for filler/overflow."""
    if isinstance(section, dict):
        return dict(section)
    return {
        "sprint_name": section.sprint_name,
        "sprint_dates": section.sprint_dates,
        "sprint_status": section.sprint_status,
        "sprint_start_date": getattr(section, "sprint_start_date", None),
        "sprint_end_date": getattr(section, "sprint_end_date", None),
        "completed": list(section.completed),
        "released": list(section.released),
        "inprogress": list(section.inprogress),
        "completed_items": list(section.completed),
        "released_items": list(section.released),
        "inprogress_items": list(section.inprogress),
        "continued_section": section.continued_section,
        "omit_category_headers": list(section.omit_category_headers),
    }


def substitute_placeholders_on_slide(slide, context: PlaceholderContext) -> int:
    """Replace {Token} placeholders in every text frame on a slide."""
    from app.services.ppt_shape_utils import iter_all_shapes

    _restore_highlights_week_header_if_needed(slide)
    updated = 0
    for shape in iter_all_shapes(slide.shapes):
        if shape.has_text_frame:
            if substitute_placeholders_in_shape_text_frame(shape, context):
                updated += 1
        if not shape.has_table:
            continue
        for row in shape.table.rows:
            for cell in row.cells:
                tf = getattr(cell, "text_frame", None)
                if tf and substitute_placeholders_in_shape_text_frame(cell, context):
                    updated += 1
    return updated


_HIGHLIGHTS_WEEK_ENDING_HEADER = "Highlights of week ending { Week End Date }"


def _set_shape_text_preserve_style(shape, text: str) -> None:
    tf = shape.text_frame
    if not tf.paragraphs:
        tf.text = text
        return
    paragraph = tf.paragraphs[0]
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = text


def _restore_highlights_week_header_if_needed(slide) -> None:
    """Revert mistaken 'Highlights for week start – end' headers to week-ending only."""
    from app.services.ppt_shape_utils import iter_all_shapes

    for shape in iter_all_shapes(slide.shapes):
        if not shape.has_table:
            continue
        try:
            cell = shape.table.cell(0, 0)
        except (IndexError, ValueError):
            continue
        text = (cell.text or "").strip()
        lower = text.lower()
        if "highlights" not in lower:
            continue
        if lower.startswith("highlights of week ending"):
            continue
        if lower.startswith("highlights for week"):
            _set_shape_text_preserve_style(cell, _HIGHLIGHTS_WEEK_ENDING_HEADER)


def sync_delivery_slide_week_dates(
    prs,
    report_start_date: str | date | None,
    report_end_date: str | date | None,
) -> int:
    """
    Fill { Week Start Date } / { Week End Date } on delivery-status slides from
    the report period (--start-date / --end-date on generate_ppt_content).
    """
    from datetime import date as date_type

    from app.services.ppt_shape_utils import is_contd_title, is_delivery_slide_title, slide_title_text

    if not report_start_date or not report_end_date:
        return 0

    start = (
        report_start_date
        if isinstance(report_start_date, date_type)
        else date_type.fromisoformat(str(report_start_date)[:10])
    )
    end = (
        report_end_date
        if isinstance(report_end_date, date_type)
        else date_type.fromisoformat(str(report_end_date)[:10])
    )
    context = PlaceholderContext.from_report_period(start, end)

    updated = 0
    for slide in prs.slides:
        title = slide_title_text(slide)
        if not is_delivery_slide_title(title) and not is_contd_title(title):
            continue
        updated += substitute_placeholders_on_slide(slide, context)
    return updated
