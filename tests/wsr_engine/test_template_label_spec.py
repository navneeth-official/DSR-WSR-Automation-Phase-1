"""Tests for template-derived paragraph label classification."""

from __future__ import annotations

from app.services.template_label_spec import (
    TemplateLabelSpec,
    anchor_needle,
    classify_paragraphs,
    normalize_label_text,
)


def _para(text: str, level: int = 0, bullet_font: str = "") -> dict:
    return {"text": text, "level": level, "bullet_font": bullet_font}


def test_normalize_label_text_strips_placeholders() -> None:
    assert normalize_label_text("{ Sprint Name }, { Status }") == ","


def test_classify_this_week_sprint_status_from_template_spec() -> None:
    spec = TemplateLabelSpec(
        template_file="test.pptx",
        current_week_texts=frozenset({"this week sprint status"}),
        category_completed_needles=frozenset({"stories completed this week"}),
        category_released_needles=frozenset({"released for partner review"}),
        category_inprogress_needles=frozenset({"stories in-progress"}),
        category_header_level=7,
        story_item_level=1,
    )
    paras = [
        _para("Sprint – Demo, In-progress (Jan 1 – Jan 7) Stories (Total – 3, Done – 1, In-review – 1, In-progress – 1)"),
        _para("This week sprint status"),
        _para("Stories completed this week – 1 stories", level=7, bullet_font="Wingdings"),
        _para("Generate Avro schema", level=1),
    ]
    classify_paragraphs(paras, spec)
    assert paras[0]["role"] == "sprint_line"
    assert paras[1]["role"] == "current_week"
    assert paras[2]["role"] == "category_completed"
    assert paras[3]["role"] == "story_item"


def test_classify_without_spec_uses_structure() -> None:
    paras = [
        _para("Sprint – Demo, In-progress (Jan 1 – Jan 7) Stories (Total – 1, Done – 0, In-review – 0, In-progress – 1)"),
        _para("This week sprint status"),
        _para("Stories completed this week – 1 stories", level=7, bullet_font="Wingdings"),
        _para("Story title", level=1),
    ]
    classify_paragraphs(paras, None)
    assert paras[0]["role"] == "sprint_line"
    assert paras[1]["role"] == "current_week"
    assert paras[2]["role"] == "category_completed"
    assert paras[3]["role"] == "story_item"


def test_classify_generic_template_level1_bold_category_headers() -> None:
    """Generic WSR template: category headers at level 1 (bold), stories at level 2."""
    spec = TemplateLabelSpec(
        template_file="test.pptx",
        current_week_texts=frozenset({"current week sprint status"}),
        category_completed_needles=frozenset({"stories completed this week – stories"}),
        category_inprogress_needles=frozenset({"stories in-progress this week – stories"}),
        category_header_level=1,
        story_item_level=2,
    )
    paras = [
        _para("Sprint – Q3.01 FY26 Atlas, Ended (Jun 1 – Jun 7) Stories (Total – 2, Completed – 2, In-Progress – 0, In-Review – 0)"),
        _para("Current week sprint status"),
        _para("Stories completed this week – 2 stories", level=1),
        _para("Validate buyer funding validation logic", level=2),
        _para("Stories in-progress this week – 1 stories", level=1),
        _para("Add API endpoint to expose cost element breakdown", level=2),
    ]
    classify_paragraphs(paras, spec)
    assert paras[2]["role"] == "category_completed"
    assert paras[3]["role"] == "story_item"
    assert paras[4]["role"] == "category_inprogress"
    assert paras[5]["role"] == "story_item"


def test_anchor_needle_shortens_long_category_header() -> None:
    needle = anchor_needle("Stories completed this week – { Count } stories")
    assert "stories completed this week" in needle
    assert "{" not in needle
