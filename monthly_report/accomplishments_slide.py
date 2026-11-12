"""Fill the Accomplishments slide.

The slide is whichever one holds ``Statement 1``, ``Statement 2`` ... placeholder
paragraphs (plain or as ``{{Statement 1}}``), in a text box or a table cell. Each
bullet takes the formatting of the statement placeholder it replaces; extra bullets
copy the last placeholder.
"""

from __future__ import annotations

import re
from copy import deepcopy

from pptx.oxml.ns import qn

from monthly_report.accomplishments_summarizer import AccomplishmentsSummary
from monthly_report.tokens import iter_text_frames, replace_tokens_in_shapes, tokens_in_shapes

_STATEMENT_PLACEHOLDER_RE = re.compile(r"^\s*(\{\{\s*)?statement\s*\d+\s*(\}\})?\s*$", re.I)
_IN_PROGRESS_PREFIX_RE = re.compile(r"^\(in progress\)\s*", re.I)


def _statement_paragraphs(text_frame) -> list:
    return [p for p in text_frame.paragraphs if _STATEMENT_PLACEHOLDER_RE.match(p.text or "")]


def _statement_text_frame(slide):
    for text_frame in iter_text_frames(slide.shapes):
        if _statement_paragraphs(text_frame):
            return text_frame
    return None


def is_accomplishments_slide(slide) -> bool:
    return _statement_text_frame(slide) is not None


def find_accomplishments_slide(prs):
    for slide in prs.slides:
        if is_accomplishments_slide(slide):
            return slide
    raise ValueError(
        "No Accomplishments slide in template (needs 'Statement 1', 'Statement 2' ... placeholders)"
    )


def _normalize_display_line(line: str) -> str:
    cleaned = _IN_PROGRESS_PREFIX_RE.sub("", (line or "").strip())
    return cleaned.strip("-• ")


def _first_text_run(p_elem):
    runs = p_elem.findall(qn("a:r"))
    return next((r for r in runs if (r.findtext(qn("a:t")) or "").strip()), runs[0] if runs else None)


def _write_paragraph(p_elem, text: str, style_p) -> None:
    """Make ``p_elem`` one run of ``text`` styled like ``style_p``'s placeholder run."""
    style_run = _first_text_run(style_p)
    style_ppr = style_p.find(qn("a:pPr"))

    for child in list(p_elem):
        if child.tag in (qn("a:r"), qn("a:br"), qn("a:fld"), qn("a:pPr")):
            p_elem.remove(child)
    if style_ppr is not None:
        p_elem.insert(0, deepcopy(style_ppr))

    run = deepcopy(style_run) if style_run is not None else p_elem.makeelement(qn("a:r"), {})
    for child in list(run):
        if child.tag != qn("a:rPr"):
            run.remove(child)
    t = run.makeelement(qn("a:t"), {})
    t.text = text
    run.append(t)
    end = p_elem.find(qn("a:endParaRPr"))
    if end is not None:
        end.addprevious(run)
    else:
        p_elem.append(run)


def _write_accomplishment_bullets(text_frame, lines: list[str]) -> None:
    display = [d for d in (_normalize_display_line(line) for line in lines) if d]
    placeholders = [p._p for p in _statement_paragraphs(text_frame)]
    if not placeholders:
        return
    styles = [deepcopy(p) for p in placeholders]

    last = placeholders[0]
    for index, text in enumerate(display):
        style = styles[min(index, len(styles) - 1)]
        if index < len(placeholders):
            target = placeholders[index]
        else:
            target = deepcopy(style)
            last.addnext(target)
        _write_paragraph(target, text, style)
        last = target

    unused = placeholders[len(display):]
    for p_elem in unused:
        if len(text_frame._txBody.findall(qn("a:p"))) > 1:
            p_elem.getparent().remove(p_elem)
        else:
            _write_paragraph(p_elem, "", styles[0])


def fill_accomplishments_slide(
    slide,
    *,
    project_title: str,
    summary: AccomplishmentsSummary,
    max_lines: int = 6,
) -> None:
    """Replace slide placeholders and write one accomplishment per statement placeholder."""
    replace_tokens_in_shapes(slide.shapes, {"project_name": project_title})
    text_frame = _statement_text_frame(slide)
    if text_frame is None:
        raise ValueError("Accomplishments statement placeholders not found")
    _write_accomplishment_bullets(text_frame, summary.slide_lines(max_lines=max_lines))


def leftover_accomplishments_tokens(slide) -> list[str]:
    return tokens_in_shapes(slide.shapes)


def strip_statement_placeholders(text: str) -> bool:
    return bool(re.search(r"statement\s*\d", text, re.I))
