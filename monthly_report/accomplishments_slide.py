"""Fill the monthly template Accomplishments table slide."""

from __future__ import annotations

import re

from monthly_report.accomplishments_summarizer import AccomplishmentsSummary
from monthly_report.text_format import (
    copy_paragraph_properties,
    copy_run_properties,
)
from monthly_report.tokens import replace_tokens_in_text_frame

_STATEMENT_PLACEHOLDER_RE = re.compile(r"^statement\s*\d+\s*$", re.I)
_IN_PROGRESS_PREFIX_RE = re.compile(r"^\(in progress\)\s*", re.I)


def is_accomplishments_slide(slide) -> bool:
    for shape in slide.shapes:
        if not getattr(shape, "has_table", False) or not shape.has_table:
            continue
        header = shape.table.cell(0, 0).text.lower()
        if "accomplishment" in header:
            return True
    return False


def find_accomplishments_slide(prs):
    for slide in prs.slides:
        if is_accomplishments_slide(slide):
            return slide
    raise ValueError("No Accomplishments slide (table with Accomplishments header) in template")


def _accomplishments_body_cell(slide):
    for shape in slide.shapes:
        if not shape.has_table:
            continue
        table = shape.table
        if len(table.rows) < 2:
            continue
        if "accomplishment" in table.cell(0, 0).text.lower():
            return table.cell(1, 0)
    return None


def _set_paragraph_text_keep_format(paragraph, text: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run().text = text


def _append_bullet_paragraph(text_frame, prototype_paragraph):
    paragraph = text_frame.add_paragraph()
    copy_paragraph_properties(paragraph, prototype_paragraph)
    if prototype_paragraph.runs:
        run = paragraph.add_run()
        copy_run_properties(run, prototype_paragraph.runs[0])
        run.text = ""
    return paragraph


def _uniform_body_paragraph_styles(text_frame) -> None:
    """Every filled bullet uses the same font/size as the first template line."""
    paragraphs = [p for p in text_frame.paragraphs if p.text.strip()]
    if not paragraphs:
        return
    prototype = paragraphs[0]
    if not prototype.runs:
        return
    proto_run = prototype.runs[0]
    for paragraph in paragraphs:
        copy_paragraph_properties(paragraph, prototype)
        if not paragraph.runs:
            run = paragraph.add_run()
            copy_run_properties(run, proto_run)
            continue
        copy_run_properties(paragraph.runs[0], proto_run)
        for extra in paragraph.runs[1:]:
            copy_run_properties(extra, proto_run)


def _normalize_display_line(line: str) -> str:
    cleaned = _IN_PROGRESS_PREFIX_RE.sub("", (line or "").strip())
    cleaned = cleaned.strip("-• ")
    return cleaned


def _write_accomplishment_bullets(cell, lines: list[str]) -> None:
    """
    Write one bullet per paragraph, preserving template bullet color/indent (Statement 1…3).
    """
    display = [_normalize_display_line(line) for line in lines if _normalize_display_line(line)]
    tf = cell.text_frame
    if not display:
        for paragraph in tf.paragraphs:
            _set_paragraph_text_keep_format(paragraph, "")
        return

    if not tf.paragraphs:
        tf.text = display[0]
        for line in display[1:]:
            tf.add_paragraph().text = line
        return

    prototype = tf.paragraphs[0]
    while len(tf.paragraphs) < len(display):
        _append_bullet_paragraph(tf, prototype)

    for index, line in enumerate(display):
        _set_paragraph_text_keep_format(tf.paragraphs[index], line)

    for index in range(len(display), len(tf.paragraphs)):
        text = tf.paragraphs[index].text.strip()
        if _STATEMENT_PLACEHOLDER_RE.match(text) or not text:
            _set_paragraph_text_keep_format(tf.paragraphs[index], "")

    _uniform_body_paragraph_styles(tf)


def fill_accomplishments_slide(
    slide,
    *,
    project_title: str,
    summary: AccomplishmentsSummary,
    max_lines: int = 6,
) -> None:
    """Replace project tokens and write cadence-style accomplishment bullets."""
    for shape in slide.shapes:
        if shape.has_text_frame:
            replace_tokens_in_text_frame(shape.text_frame, {"project_name": project_title})

    cell = _accomplishments_body_cell(slide)
    if cell is None:
        raise ValueError("Accomplishments body cell not found")

    lines = summary.slide_lines(max_lines=max_lines)
    _write_accomplishment_bullets(cell, lines)


def leftover_accomplishments_tokens(slide) -> list[str]:
    from monthly_report.tokens import find_tokens

    found: list[str] = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            found.extend(find_tokens(shape.text_frame.text))
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    found.extend(find_tokens(cell.text_frame.text))
    return found


def strip_statement_placeholders(text: str) -> bool:
    return bool(re.search(r"statement\s*\d", text, re.I))
