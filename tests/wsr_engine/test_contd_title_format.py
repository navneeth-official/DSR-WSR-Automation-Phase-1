"""Tests for delivery slide title formatting on continuation slides."""

from __future__ import annotations

import copy

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

from app.services.ppt_shape_utils import find_title_shape
from app.services.template_content_filler import (
    apply_delivery_title_preserve_format,
    set_contd_title_from_reference,
    visible_title_text,
)


def _add_title_shape(slide, paragraphs: list[tuple[str, str | None]]) -> object:
    """paragraphs: list of (text, sz attribute value e.g. '1600' or None)."""
    shape = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(0.6))
    shape.name = "Title 1"
    tf = shape.text_frame
    tf.clear()
    for idx, (text, sz) in enumerate(paragraphs):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        run = p.add_run()
        run.text = text
        if sz is not None:
            r_pr = run._r.get_or_add_rPr()
            r_pr.set("sz", sz)
    return shape


def test_visible_title_text_skips_leading_blank_paragraph() -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    shape = _add_title_shape(slide, [("", None), ("Delivery status – Demo", "1600")])
    assert visible_title_text(shape) == "Delivery status – Demo"


def test_set_contd_title_from_reference_copies_run_formatting() -> None:
    prs = Presentation()
    main = prs.slides.add_slide(prs.slide_layouts[6])
    contd = prs.slides.add_slide(prs.slide_layouts[6])
    ref = _add_title_shape(main, [("", None), ("Delivery status – Cost Core Service", "1600")])

    set_contd_title_from_reference(contd, ref, contd_marker="(Contd..)")
    contd_title = find_title_shape(contd)

    assert contd_title.text.strip().endswith("(Contd..)")
    styled_para = next(p for p in contd_title.text_frame.paragraphs if p.text.strip())
    r_pr = styled_para.runs[0]._r.find(qn("a:rPr"))
    assert r_pr is not None
    assert r_pr.get("sz") == "1600"


def test_apply_delivery_title_preserve_format_matches_reference_paragraph_layout() -> None:
    prs = Presentation()
    main = prs.slides.add_slide(prs.slide_layouts[6])
    target = prs.slides.add_slide(prs.slide_layouts[6])
    ref = _add_title_shape(main, [("", None), ("Delivery status – Demo", "1600")])

    apply_delivery_title_preserve_format(target, "Delivery status – Demo  (Contd..)", ref)
    contd_title = find_title_shape(target)

    assert len(contd_title.text_frame.paragraphs) == len(ref.text_frame.paragraphs)
    assert _content_paragraph_index(contd_title) == _content_paragraph_index(ref)
    assert contd_title.top == ref.top
    assert contd_title.left == ref.left
    assert contd_title.width == ref.width
    assert contd_title.height == ref.height
    assert "(Contd..)" in visible_title_text(contd_title)


def _content_paragraph_index(title_shape) -> int:
    from app.services.template_content_filler import _content_paragraph_index as idx

    return idx(title_shape)
