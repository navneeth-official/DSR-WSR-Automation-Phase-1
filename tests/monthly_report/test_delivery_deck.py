from datetime import date

import pytest
from pptx import Presentation
from pptx.enum.dml import MSO_FILL_TYPE

from monthly_report.config import REPO_ROOT, MONTHLY_TEMPLATES_DIR
from monthly_report.deck import ProjectSection, build_monthly_cadence_deck, build_monthly_deck
from monthly_report.index_slide import find_index_slide_index
from monthly_report.delivery_slide import (
    ENDED_TABLE,
    IN_PROGRESS_TABLE,
    analyze_delivery_slide,
    find_delivery_slide,
    format_schedule_date,
    is_delivery_slide,
    table_kind,
)
from monthly_report.metrics import ENDED, IN_PROGRESS, SprintMetrics

# Pin to the Pricing cadence fixture (3 slots, Spill Over). Newest monthly
# templates may use Carry Over / 2 slots — covered separately below.
_PRICING_CANDIDATES = (
    MONTHLY_TEMPLATES_DIR / "G10X_H-E-B_Pricing cadence Meeting Template.pptx",
    REPO_ROOT / "G10X_H-E-B_Pricing cadence Meeting Template.pptx",
)
TEMPLATE = next((p for p in _PRICING_CANDIDATES if p.is_file()), None)
MSR_TEMPLATE_TWO = MONTHLY_TEMPLATES_DIR / "G10X_H-E-B_MSR_Template_two.pptx"

pytestmark = pytest.mark.skipif(
    TEMPLATE is None,
    reason="Pricing cadence monthly template missing",
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


def test_pricing_template_maps_in_review_series_to_rc_not_sc():
    """Mixed {{SC}}/{{RC}} data-label tokens must not steal the In-Review series."""
    from monthly_report.delivery_slide import _series_metrics_for_chart

    prs = Presentation(str(TEMPLATE))
    template = analyze_delivery_slide(find_delivery_slide(prs))
    chart = template.chart_frame.chart
    names = [s.name for s in chart.plots[0].series]
    metrics = _series_metrics_for_chart(chart, names, template.metric_labels)
    by_name = dict(zip(names, metrics))
    assert by_name["Completed"] == "cc"
    assert by_name["In-Review"] == "rc"
    assert by_name["In-Progress"] == "pc"
    assert by_name["Spill Over"] == "sc"


def test_chart_hides_rc_pc_on_ended_when_spill_series_exists():
    from monthly_report.delivery_slide import _chart_point_value

    ended = SPRINT_ENDED_SPILL
    running = SPRINT_RUNNING
    assert _chart_point_value(ended, "rc", has_spill_series=True) is None
    assert _chart_point_value(ended, "pc", has_spill_series=True) is None
    assert _chart_point_value(ended, "sc", has_spill_series=True) == 3.0
    assert _chart_point_value(running, "rc", has_spill_series=True) == 3.0
    assert _chart_point_value(running, "pc", has_spill_series=True) == 1.0
    assert _chart_point_value(running, "sc", has_spill_series=True) is None


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
    assert plot.gap_width == 150
    values = {s.name: list(s.values) for s in plot.series}
    # Ended sprints: unfinished work only on Spill Over (matches ended table).
    # In-progress: In-Review / In-Progress segments (matches in-progress table).
    assert values["Completed"] == [8.0, 3.0, 2.0]
    assert values["In-Review"] == [None, None, 3.0]
    assert values["In-Progress"] == [None, None, 1.0]
    assert values["Spill Over"] == [3.0, None, None]
    # Stacked totals must match table Total Stories (TC).
    for i, expected in enumerate([11.0, 3.0, 6.0]):
        stacked = sum(values[name][i] or 0.0 for name in values)
        assert stacked == expected


def test_unused_slots_are_removed(tmp_path):
    out = tmp_path / "deck.pptx"
    _build(out, "Pricing Core", [SPRINT_RUNNING])
    _, slides = _delivery_slides(out)
    assert [table_kind(t) for t in _sprint_tables(slides[0])] == [IN_PROGRESS_TABLE]
    cats = list(_chart(slides[0]).plots[0].categories)
    assert cats[0] == "Unavailable avenger"
    assert len(cats) == 3
    assert cats[1].strip() == ""
    assert cats[2].strip() == ""


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


@pytest.mark.skipif(not MSR_TEMPLATE_TWO.is_file(), reason="MSR_Template_two missing")
def test_carry_over_template_classifies_and_preserves_headers():
    prs = Presentation(str(MSR_TEMPLATE_TWO))
    slide = find_delivery_slide(prs)
    template = analyze_delivery_slide(slide)
    assert template.sprints_per_slide == 2
    assert table_kind(template.ended_table) == ENDED_TABLE
    assert table_kind(template.in_progress_table) == IN_PROGRESS_TABLE
    assert "carry over" in template.spill_series_label.lower().replace("-", " ")
    # Chart already names the series Carry-Over — do not require inventing Spill Over.
    chart_keys = {
        s.name.lower().replace("-", " ").replace("_", " ")
        for s in template.chart_frame.chart.plots[0].series
    }
    assert "carry over" in chart_keys


@pytest.mark.skipif(not MSR_TEMPLATE_TWO.is_file(), reason="MSR_Template_two missing")
def test_renamed_headers_and_moved_tables_follow_the_template(tmp_path):
    """Wording, series names and table placement come from the template, not the code."""
    from pptx.chart.data import CategoryChartData

    prs = Presentation(str(MSR_TEMPLATE_TWO))
    slide = find_delivery_slide(prs)
    template = analyze_delivery_slide(slide)
    ended, running = template.ended_table, template.in_progress_table
    for row in ended.table.rows:
        for cell in row.cells:
            if cell.text.strip() == "Carry Over":
                cell.text_frame.paragraphs[0].runs[0].text = "Leftover Work"
                for run in cell.text_frame.paragraphs[0].runs[1:]:
                    run.text = ""
    running.left, running.top = ended.left + ended.width, ended.top
    chart = template.chart_frame.chart
    data = CategoryChartData()
    data.categories = ["x"]
    for name in ("Completed", "In-Review", "In-Progress", "Leftover Work"):
        data.add_series(name, [1])
    chart.replace_data(data)
    custom = tmp_path / "custom_template.pptx"
    prs.save(str(custom))

    out = tmp_path / "custom_deck.pptx"
    result = build_monthly_deck(custom, out, "Cost", [SPRINT_ENDED_SPILL, SPRINT_RUNNING])
    assert result.leftover_tokens == {}
    _, slides = _delivery_slides(out)
    tables = sorted(
        (s for s in slides[0].shapes if table_kind(s)), key=lambda s: (s.top, s.left)
    )
    assert [table_kind(t) for t in tables] == [ENDED_TABLE, IN_PROGRESS_TABLE]
    assert tables[0].top == tables[1].top and tables[1].left > tables[0].left
    ended_labels = {
        cell.text.strip() for row in tables[0].table.rows for cell in row.cells
    }
    assert "Leftover Work" in ended_labels


@pytest.mark.skipif(not MSR_TEMPLATE_TWO.is_file(), reason="MSR_Template_two missing")
def test_single_sprint_chart_uses_template_slot_width(tmp_path):
    out = tmp_path / "one_sprint.pptx"
    _build(out, "Supplier Portal", [SPRINT_ENDED_CLEAN])
    _, slides = _delivery_slides(out)
    cats = list(_chart(slides[0]).plots[0].categories)
    assert cats[0] == "Tangent man"
    assert len(cats) == 3


def test_carry_over_template_builds_without_leftover_schedule_tokens(tmp_path):
    out = tmp_path / "carry_over_deck.pptx"
    result = build_monthly_deck(
        MSR_TEMPLATE_TWO,
        out,
        "Cost Core Service",
        [SPRINT_ENDED_SPILL, SPRINT_RUNNING],
        index_reference_path=None,
    )
    assert result.leftover_tokens == {}
    _, slides = _delivery_slides(out)
    assert len(slides) == 1
    tables = _sprint_tables(slides[0])
    assert [table_kind(t) for t in tables] == [ENDED_TABLE, IN_PROGRESS_TABLE]
    ended = tables[0].table
    ended_labels = {cell.text.strip() for row in ended.rows for cell in row.cells}
    assert "Carry Over" in ended_labels
    assert "Shadow lurker" in ended.cell(0, 0).text
    assert format_schedule_date(date(2026, 8, 3)) in ended.cell(2, 0).text
    values = {s.name: list(s.values) for s in _chart(slides[0]).plots[0].series}
    assert values["Carry-Over"] == [3.0, None]
    assert values["In-review"] == [None, 3.0]
    assert values["In-progress"] == [None, 1.0]
    assert values["Completed"] == [8.0, 2.0]
    assert "Spill Over" not in values
    for i, expected in enumerate([11.0, 6.0]):
        stacked = sum(values[name][i] or 0.0 for name in values)
        assert stacked == expected
