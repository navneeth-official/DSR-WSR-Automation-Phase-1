"""Week-end date placeholder substitution on WSR slides."""

from datetime import date

from pptx import Presentation
from pptx.util import Inches

from app.services.ppt_week_end_date import (
    format_week_end_date,
    replace_week_end_date_placeholders,
)


def _slide_with_header():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    table = slide.shapes.add_table(1, 1, Inches(0.5), Inches(0.5), Inches(8), Inches(0.4)).table
    cell = table.cell(0, 0)
    paragraph = cell.text_frame.paragraphs[0]
    paragraph.clear()
    for piece in (
        "Highlights",
        " ",
        "of",
        " ",
        "week",
        " ",
        "ending",
        " ",
        "{ Week End Date }",
    ):
        paragraph.add_run().text = piece
    return prs, cell


def test_format_week_end_date_uses_day_month_year():
    assert format_week_end_date(date(2026, 11, 6)) == "6 Nov 2026"
    assert format_week_end_date(date(2026, 6, 15)) == "15 Jun 2026"


def test_replaces_split_run_week_end_date_in_highlights_header():
    prs, cell = _slide_with_header()

    updated = replace_week_end_date_placeholders(prs, date(2026, 11, 6))

    assert updated == 1
    assert cell.text_frame.text == "Highlights of week ending 6 Nov 2026"
    runs = [run.text for run in cell.text_frame.paragraphs[0].runs]
    assert runs[-1] == "6 Nov 2026"
    assert "Highlights" in runs


def test_replaces_bare_and_braced_tokens_in_a_text_box():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(6), Inches(0.4))
    box.text_frame.text = "Week ending {Week End Date} / Week End Date"

    replace_week_end_date_placeholders(prs, date(2026, 6, 15))

    assert box.text_frame.text == "Week ending 15 Jun 2026 / 15 Jun 2026"


def test_replaces_placeholders_on_every_track_slide():
    prs = Presentation()
    headers = []
    for _ in range(3):
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(6), Inches(0.4))
        box.text_frame.text = "Highlights of week ending { Week End Date }"
        headers.append(box)

    updated = replace_week_end_date_placeholders(prs, date(2026, 11, 6))

    assert updated == 3
    assert [box.text_frame.text for box in headers] == [
        "Highlights of week ending 6 Nov 2026",
    ] * 3


def test_leaves_slides_without_the_placeholder_unchanged():
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(6), Inches(0.4))
    box.text_frame.text = "Highlights of week ending 05 June 2026"

    updated = replace_week_end_date_placeholders(prs, date(2026, 11, 6))

    assert updated == 0
    assert box.text_frame.text == "Highlights of week ending 05 June 2026"
