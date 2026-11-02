from datetime import date

import pytest
from pptx import Presentation

from monthly_report.config import resolve_template
from monthly_report.cover_slide import (
    cover_leftover_tokens,
    fill_cover_slide,
    format_cover_meeting_date,
)
from monthly_report.tokens import token_key

pytestmark = pytest.mark.skipif(
    not resolve_template().is_file(),
    reason="monthly template missing",
)


def test_token_keys_for_cover_placeholders():
    assert token_key("Track Name") == "track_name"
    assert token_key("TRACK NAME") == "track_name"
    assert token_key("Date") == "date"


def test_format_cover_meeting_date():
    assert format_cover_meeting_date(date(2026, 6, 20)) == "20 Jun 2026"


def test_fill_cover_slide_replaces_track_and_date():
    prs = Presentation(str(resolve_template()))
    slide = prs.slides[0]
    leftovers = fill_cover_slide(
        slide,
        track_name="Pricing",
        meeting_date=date(2026, 6, 20),
    )
    assert leftovers == []
    assert cover_leftover_tokens(slide) == []
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    assert any("Pricing" in t and "Cadence" in t for t in texts)
    assert any("20 Jun 2026" in t for t in texts)
    assert not any("{{" in t for t in texts)
