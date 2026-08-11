"""Tests for placeholder locator on real template."""

from __future__ import annotations

from pathlib import Path

import pytest
from pptx import Presentation

from app.services.ppt_shape_utils import get_highlights_shape, get_key_activities_shape
from app.wsr_engine.placeholder_locator import highlights_content_cell, locate_highlights_placeholder

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "wsr_template.pptx"
G10X = Path(__file__).resolve().parents[2] / "templates" / "G10X H-E-B WSR Sustainment 05 June 2026 .pptx"


@pytest.mark.parametrize("path", [TEMPLATE, G10X])
def test_finds_highlights_on_template(path: Path):
    if not path.is_file():
        pytest.skip(f"template missing: {path}")
    prs = Presentation(str(path))
    found = 0
    for slide in prs.slides:
        try:
            get_highlights_shape(slide)
            locate_highlights_placeholder(slide)
            highlights_content_cell(slide)
            found += 1
        except ValueError:
            continue
    assert found >= 1
