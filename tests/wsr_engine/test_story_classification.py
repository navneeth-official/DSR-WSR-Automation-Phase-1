"""Tests for story paragraph classification."""

from __future__ import annotations

from app.services.template_label_spec import classify_paragraphs


def _role(para: dict) -> str:
    classify_paragraphs([para], None)
    return para["role"]


def test_hyphen_story_at_level_zero_is_story_item() -> None:
    role = _role(
        {
            "text": "Fix grace period not applied for late punch-in",
            "level": 0,
            "bullet": "₋",
            "bullet_font": "Calibri",
        }
    )
    assert role == "story_item"


def test_level1_bold_category_header_not_story_item() -> None:
    from app.services.template_label_spec import TemplateLabelSpec, classify_paragraphs

    spec = TemplateLabelSpec(
        template_file="test.pptx",
        category_completed_needles=frozenset({"stories completed this week – stories"}),
        category_header_level=1,
        story_item_level=2,
    )
    paras = [
        {
            "text": "Stories completed this week – 2 stories",
            "level": 1,
            "bullet": "•",
            "bullet_font": "Calibri",
            "runs": [{"text": "Stories completed this week – 2 stories", "bold": True, "size_pt": 13.0}],
        },
        {
            "text": "Validate buyer funding validation logic",
            "level": 2,
            "bullet": "▪",
            "bullet_font": "Calibri",
            "runs": [{"text": "Validate buyer funding validation logic", "bold": False, "size_pt": 13.0}],
        },
    ]
    classify_paragraphs(paras, spec)
    assert paras[0]["role"] == "category_completed"
    assert paras[1]["role"] == "story_item"
