from datetime import date

import pytest
from pptx import Presentation
from pptx.enum.dml import MSO_FILL_TYPE

from monthly_report.config import resolve_template
from monthly_report.deck import ProjectSection, build_monthly_cadence_deck, build_monthly_deck
from monthly_report.index_slide import find_index_slide_index
from monthly_report.delivery_slide import (
    ENDED_TABLE,
    IN_PROGRESS_TABLE,
    format_schedule_date,
    is_delivery_slide,
    table_kind,
)
from monthly_report.metrics import ENDED, IN_PROGRESS, SprintMetrics

try:
    TEMPLATE = resolve_template()
except FileNotFoundError:
    TEMPLATE = None

pytestmark = pytest.mark.skipif(
    TEMPLATE is None,
    reason="monthly template missing",
)


def _build(out, title, sprints, **kwargs):
    return build_monthly_deck(TEMPLATE, out, title, sprints, index_reference_path=None, **kwargs)


def _sprint(name, status, start, end, total, completed, in_review=0, in_progress=0):
    spill = in_review + in_progress if status == ENDED else None
    return SprintMetrics(
        sprint_name=name,
        start_date=start,
        end_date=end,
        status=status,
        db_status=None,
        total=total,
        completed=completed,
        in_review=in_review,
        in_progress=in_progress,
        other=total - completed - in_review - in_progress,
        spill_over=spill,
    )


SPRINT_ENDED_SPILL = _sprint("Shadow lurker", ENDED, date(2026, 8, 3), date(2026, 8, 14), 11, 8, in_review=3)
SPRINT_ENDED_CLEAN = _sprint("Tangent man", ENDED, date(2026, 8, 17), date(2026, 8, 28), 3, 3)
SPRINT_RUNNING = _sprint(
    "Unavailable avenger", IN_PROGRESS, date(2026, 8, 31), date(2026, 9, 11), 6, 2, in_review=3, in_progress=1
)


def _delivery_slides(path):
    prs = Presentation(str(path))
    return prs, [s for s in prs.slides if is_delivery_slide(s)]


def _sprint_tables(slide):
    return sorted((s for s in slide.shapes if table_kind(s)), key=lambda s: s.top)


def _chart(slide):
    return next(s for s in slide.shapes if s.has_chart).chart


def test_three_sprints_fill_one_slide(tmp_path):
    out = tmp_path / "deck.pptx"
    result = _build(out, "Pricing Core", [SPRINT_ENDED_SPILL, SPRINT_ENDED_CLEAN, SPRINT_RUNNING])
    assert result.leftover_tokens == {}

    prs, slides = _delivery_slides(out)
    assert find_index_slide_index(prs) is None
    assert len(slides) == 1
    slide = slides[0]
    assert slide.shapes.title.text == "Delivery Updates: Pricing Core"

    tables = _sprint_tables(slide)
    assert [table_kind(t) for t in tables] == [ENDED_TABLE, ENDED_TABLE, IN_PROGRESS_TABLE]
    first = tables[0].table
    assert "Shadow lurker" in first.cell(0, 0).text
    schedule = first.cell(2, 0).text
    assert format_schedule_date(date(2026, 8, 3)) in schedule and "Ended" in schedule
    assert [first.cell(2, c).text for c in (1, 2, 3)] == ["11", "8", "3"]
    assert [tables[1].table.cell(2, c).text for c in (1, 2, 3)] == ["3", "3", "0"]
    running = tables[2].table
    assert "Sept 11" in running.cell(2, 0).text and "In-Progress" in running.cell(2, 0).text
    assert [running.cell(2, c).text for c in (1, 2, 3, 4)] == ["6", "2", "3", "1"]

    plot = _chart(slide).plots[0]
    assert list(plot.categories) == ["Shadow lurker", "Tangent man", "Unavailable avenger"]
    values = {s.name: list(s.values) for s in plot.series}
    assert values["Completed"] == [8, 3, 2]
    assert values["In-Review"] == [None, None, 3]
    assert values["In-Progress"] == [None, None, 1]
    assert values["Spill Over"] == [3, None, None]


def test_unused_slots_are_removed(tmp_path):
    out = tmp_path / "deck.pptx"
    _build(out, "Pricing Core", [SPRINT_RUNNING])
    _, slides = _delivery_slides(out)
    assert [table_kind(t) for t in _sprint_tables(slides[0])] == [IN_PROGRESS_TABLE]
    assert list(_chart(slides[0]).plots[0].categories) == ["Unavailable avenger"]


def test_extra_sprints_move_to_continuation_slide(tmp_path):
    out = tmp_path / "deck.pptx"
    fourth = _sprint("Fourth", IN_PROGRESS, date(2026, 8, 20), date(2026, 9, 2), 2, 1, in_progress=1)
    result = _build(
        out, "Pricing Core", [SPRINT_ENDED_SPILL, SPRINT_ENDED_CLEAN, SPRINT_RUNNING, fourth]
    )
    assert len(result.delivery_slide_numbers) == 2
    assert result.delivery_slide_numbers == sorted(result.delivery_slide_numbers)
    assert result.leftover_tokens == {}
    prs, slides = _delivery_slides(out)
    assert find_index_slide_index(prs) is None
    assert len(slides) >= 2
    assert slides[0].shapes.title.text == "Delivery Updates: Pricing Core"
    assert "(Contd.)" in slides[1].shapes.title.text
    assert len(_sprint_tables(slides[0])) == 3
    assert len(_sprint_tables(slides[1])) == 1

    for slide in slides:
        for series in _chart(slide).plots[0].series:
            if series.name == "Spill Over":
                continue
            assert series.format.fill.type == MSO_FILL_TYPE.SOLID


def test_no_sprints_removes_delivery_slide(tmp_path):
    out = tmp_path / "deck.pptx"
    result = _build(out, "Pricing Core", [])
    prs, slides = _delivery_slides(out)
    assert slides == []
    assert find_index_slide_index(prs) is None
    assert len(prs.slides) == 2
    assert result.warnings


def test_all_projects_in_one_deck(tmp_path):
    out = tmp_path / "combined.pptx"
    result = build_monthly_cadence_deck(
        TEMPLATE,
        out,
        [
            ProjectSection("PRC", "Pricing Core", [SPRINT_RUNNING]),
            ProjectSection("LOC", "LOCO", [SPRINT_ENDED_CLEAN]),
        ],
        use_accomplishments=False,
    )
    assert result.projects_included == ["PRC", "LOC"]
    assert result.index_entries_updated == 0

    assert len(result.delivery_slide_numbers) == 2
    assert result.delivery_slide_numbers == sorted(result.delivery_slide_numbers)

    prs = Presentation(str(out))
    assert find_index_slide_index(prs) is None
    assert len([s for s in prs.slides if is_delivery_slide(s)]) == 2
