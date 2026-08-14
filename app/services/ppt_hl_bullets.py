"""Preserve Highlights story-line bullet styles from template paragraphs."""

from __future__ import annotations

from pptx.oxml.ns import qn

from app.services.ppt_shape_utils import paragraph_text

STORY_TEXT_PREFIX_CHARS = ("\u208b", "-", "\u2013")  # ₋, hyphen, en dash


def paragraph_has_xml_bullet(p_elem) -> bool:
    p_pr = p_elem.find(qn("a:pPr"))
    if p_pr is None:
        return False
    return p_pr.find(qn("a:buChar")) is not None or p_pr.find(qn("a:buAutoNum")) is not None


def _story_prefix_content_runs(p_elem) -> tuple | None:
    """Return (prefix_run, content_run) when bullet is a literal prefix character in text."""
    runs = p_elem.findall(qn("a:r"))
    if len(runs) < 2:
        return None
    t0 = runs[0].find(qn("a:t"))
    t1 = runs[1].find(qn("a:t"))
    if t0 is None or t1 is None:
        return None
    if (t0.text or "") not in STORY_TEXT_PREFIX_CHARS:
        return None
    return runs[0], runs[1]


def set_story_line_text(p_elem, text: str) -> None:
    """
    Set story body text without dropping template bullet formatting.

    Some G10X templates use buChar bullets; others embed ₋/`-` as the first
    text run followed by a tab + body run.
    """
    prefix_runs = _story_prefix_content_runs(p_elem)
    if prefix_runs is not None and not paragraph_has_xml_bullet(p_elem):
        _, content_run = prefix_runs
        content_run.find(qn("a:t")).text = f"\t{text}"
        runs = p_elem.findall(qn("a:r"))
        idx = runs.index(content_run)
        for extra in runs[idx + 1 :]:
            p_elem.remove(extra)
        return

    set_single_run_text(p_elem, text)


def clear_story_line_text(p_elem) -> None:
    set_story_line_text(p_elem, "")


def set_single_run_text(p_elem, text: str) -> None:
    runs = p_elem.findall(qn("a:r"))
    if not runs:
        return
    runs[0].find(qn("a:t")).text = text
    for extra in runs[1:]:
        p_elem.remove(extra)


def is_text_prefix_story_bullet(p_elem) -> bool:
    text = paragraph_text(p_elem).strip()
    if text.startswith(STORY_TEXT_PREFIX_CHARS):
        return True
    return _story_prefix_content_runs(p_elem) is not None
