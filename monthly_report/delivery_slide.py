"""Fill the "Delivery Updates: {{Project Name}}" slide: sprint tables and status chart."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.dml import MSO_FILL_TYPE, MSO_THEME_COLOR
from pptx.oxml.ns import qn
from pptx.shapes.graphfrm import GraphicFrame

from monthly_report.metrics import SprintMetrics
from monthly_report.slide_ops import duplicate_slide
from monthly_report.text_format import uniform_run_fonts_in_row
from monthly_report.tokens import find_tokens, replace_tokens_in_text_frame

ENDED_TABLE = "ended"
IN_PROGRESS_TABLE = "in_progress"

SPILL_OVER_SERIES = "Spill Over"
CONTINUATION_SUFFIX = " (Contd.)"
WHOLE_NUMBER_AXIS_MAX = 10

_MONTH_ABBREVIATIONS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sept", "Oct", "Nov", "Dec",
)


def format_schedule_date(value: date) -> str:
    return f"{_MONTH_ABBREVIATIONS[value.month - 1]} {value.day:02d}"


def _normalize_label(text: str) -> str:
    return re.sub(r"[\s_-]+", " ", (text or "").strip().lower())


def _table_labels(frame) -> set[str]:
    table = frame.table
    return {_normalize_label(cell.text) for row in table.rows for cell in row.cells}


def table_kind(frame) -> str | None:
    """Ended tables carry a Spill Over column; in-progress tables an In-progress column."""
    if not getattr(frame, "has_table", False) or not frame.has_table:
        return None
    labels = _table_labels(frame)
    if "spill over" in labels:
        return ENDED_TABLE
    if "in progress" in labels:
        return IN_PROGRESS_TABLE
    return None


@dataclass
class DeliveryTemplate:
    chart_frame: GraphicFrame
    ended_table: GraphicFrame
    in_progress_table: GraphicFrame
    table_frames: list[GraphicFrame]
    slot_tops: list[int]
    series_theme_colors: dict[str, MSO_THEME_COLOR]

    @property
    def sprints_per_slide(self) -> int:
        return len(self.slot_tops)


def is_delivery_slide(slide) -> bool:
    has_chart = any(getattr(s, "has_chart", False) and s.has_chart for s in slide.shapes)
    return has_chart and any(table_kind(s) for s in slide.shapes)


def find_delivery_slide(prs):
    for slide in prs.slides:
        if is_delivery_slide(slide):
            return slide
    raise ValueError("No Delivery Updates slide (chart + sprint snapshot tables) in template")


def analyze_delivery_slide(slide) -> DeliveryTemplate:
    tables = sorted((s for s in slide.shapes if table_kind(s)), key=lambda s: s.top)
    ended = next((t for t in tables if table_kind(t) == ENDED_TABLE), None)
    in_progress = next((t for t in tables if table_kind(t) == IN_PROGRESS_TABLE), None)
    if ended is None or in_progress is None:
        raise ValueError("Delivery slide needs one Spill Over table and one In-progress table")
    chart_frame = next(s for s in slide.shapes if getattr(s, "has_chart", False) and s.has_chart)
    return DeliveryTemplate(
        chart_frame=chart_frame,
        ended_table=ended,
        in_progress_table=in_progress,
        table_frames=tables,
        slot_tops=[t.top for t in tables],
        series_theme_colors=_capture_series_theme_colors(chart_frame.chart),
    )


def duplicate_delivery_slide(prs, source, template: DeliveryTemplate):
    """
    Copy the delivery slide.

    The chart is recreated with ``add_chart`` (copying the chart XML duplicates
    workbook parts and corrupts the .pptx). Template series colors are restored
    in ``fill_chart`` via ``series_theme_colors``.
    """
    new_slide = duplicate_slide(
        prs, source, skip_shape_ids=frozenset({template.chart_frame.shape_id})
    )
    _clone_chart(template.chart_frame, new_slide)
    return new_slide


def _clone_chart(source_frame: GraphicFrame, slide) -> GraphicFrame:
    placeholder = CategoryChartData()
    placeholder.categories = ["-"]
    placeholder.add_series("Completed", [0])
    placeholder.add_series("In-Review", [0])
    placeholder.add_series("In-Progress", [0])
    frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_STACKED,
        source_frame.left,
        source_frame.top,
        source_frame.width,
        source_frame.height,
        placeholder,
    )
    frame.name = source_frame.name
    return frame


def _capture_series_theme_colors(chart) -> dict[str, MSO_THEME_COLOR]:
    colors: dict[str, MSO_THEME_COLOR] = {}
    for series in chart.plots[0].series:
        key = _series_key(series.name)
        try:
            fill = series.format.fill
            if fill.type == MSO_FILL_TYPE.SOLID:
                colors[key] = fill.fore_color.theme_color
        except (TypeError, AttributeError, ValueError):
            continue
    return colors


def _apply_series_theme_colors(chart, theme_colors: dict[str, MSO_THEME_COLOR]) -> None:
    for series in chart.plots[0].series:
        theme = theme_colors.get(_series_key(series.name))
        if theme is None:
            continue
        series.format.fill.solid()
        series.format.fill.fore_color.theme_color = theme


def _sprint_values(sprint: SprintMetrics) -> dict[str, str]:
    return {
        "sprint_name": sprint.sprint_name,
        "start_date": format_schedule_date(sprint.start_date),
        "end_date": format_schedule_date(sprint.end_date),
        "status": sprint.status,
        "tc": str(sprint.total),
        "cc": str(sprint.completed),
        "rc": str(sprint.in_review),
        "pc": str(sprint.in_progress),
        "sc": str(sprint.spill_over) if sprint.spill_over is not None else "",
    }


def _place_sprint_table(slide, prototype: GraphicFrame, top: int, shape_id: int, name: str) -> GraphicFrame:
    element = deepcopy(prototype._element)
    c_nv_pr = element.nvGraphicFramePr.cNvPr
    c_nv_pr.id = shape_id
    c_nv_pr.name = name
    slide.shapes._spTree.insert_element_before(element, "p:extLst")
    frame = GraphicFrame(element, slide.shapes)
    frame.top = top
    return frame


def _fill_table(frame: GraphicFrame, values: dict[str, str]) -> None:
    table = frame.table
    for row in table.rows:
        for cell in row.cells:
            replace_tokens_in_text_frame(cell.text_frame, values)
    if len(table.rows) >= 3:
        uniform_run_fonts_in_row(table, 2)


def _series_key(name: str) -> str:
    return _normalize_label(name).replace(" ", "_")


def _chart_value(sprint: SprintMetrics, series_key: str) -> int | None:
    if sprint.is_ended:
        value = {"completed": sprint.completed, "spill_over": sprint.spill_over}.get(series_key)
    else:
        value = {
            "completed": sprint.completed,
            "in_review": sprint.in_review,
            "in_progress": sprint.in_progress,
        }.get(series_key)
    return value or None


def _detach_linked_workbook(chart) -> None:
    """Drop a link to an external workbook so replace_data embeds the data in the deck."""
    external_data = chart._chartSpace.find(qn("c:externalData"))
    if external_data is None:
        return
    r_id = external_data.get(qn("r:id"))
    if chart.part.rels[r_id].is_external:
        chart._chartSpace.remove(external_data)
        chart.part.drop_rel(r_id)


def _remove_custom_point_labels(chart) -> None:
    for d_lbls in chart._chartSpace.iter(qn("c:dLbls")):
        for d_lbl in d_lbls.findall(qn("c:dLbl")):
            d_lbls.remove(d_lbl)


def _style_spill_over_series(series) -> None:
    for d_pt in series._element.findall(qn("c:dPt")):
        series._element.remove(d_pt)
    series.format.fill.solid()
    series.format.fill.fore_color.theme_color = MSO_THEME_COLOR.ACCENT_6
    series.data_labels.font.color.theme_color = MSO_THEME_COLOR.TEXT_1


def fill_chart(
    chart,
    sprints: list[SprintMetrics],
    series_theme_colors: dict[str, MSO_THEME_COLOR] | None = None,
) -> None:
    """One category per sprint; ended sprints show Completed + Spill Over only."""
    names = [series.name for series in chart.plots[0].series]
    keys = [_series_key(name) for name in names]
    add_spill_over = "spill_over" not in keys
    if add_spill_over:
        names.append(SPILL_OVER_SERIES)
        keys.append("spill_over")

    data = CategoryChartData()
    data.categories = [sprint.sprint_name for sprint in sprints]
    columns = [[_chart_value(sprint, key) for sprint in sprints] for key in keys]
    for name, values in zip(names, columns):
        data.add_series(name, values)

    _detach_linked_workbook(chart)
    _remove_custom_point_labels(chart)
    chart.replace_data(data)
    if series_theme_colors:
        _apply_series_theme_colors(chart, series_theme_colors)
    if add_spill_over:
        _style_spill_over_series(chart.plots[0].series[-1])

    tallest_bar = max((sum(v or 0 for v in bar) for bar in zip(*columns)), default=0)
    chart.value_axis.major_unit = 1 if tallest_bar <= WHOLE_NUMBER_AXIS_MAX else None


def leftover_tokens(slide) -> list[str]:
    found: list[str] = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            found.extend(find_tokens(shape.text_frame.text))
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    found.extend(find_tokens(cell.text))
    return found


def fill_delivery_slide(
    slide,
    project_title: str,
    sprints: list[SprintMetrics],
    *,
    series_theme_colors: dict[str, MSO_THEME_COLOR] | None = None,
) -> list[str]:
    """Fill one delivery slide with up to ``sprints_per_slide`` sprints; return leftover tokens."""
    template = analyze_delivery_slide(slide)
    theme_colors = series_theme_colors or template.series_theme_colors
    if len(sprints) > template.sprints_per_slide:
        raise ValueError(
            f"{len(sprints)} sprints given; slide holds {template.sprints_per_slide}"
        )

    for shape in slide.shapes:
        if shape.has_text_frame:
            replace_tokens_in_text_frame(shape.text_frame, {"project_name": project_title})

    next_id = max(shape.shape_id for shape in slide.shapes) + 1
    for position, sprint in enumerate(sprints):
        prototype = template.ended_table if sprint.is_ended else template.in_progress_table
        frame = _place_sprint_table(
            slide,
            prototype,
            template.slot_tops[position],
            next_id + position,
            f"Sprint Table {position + 1}",
        )
        _fill_table(frame, _sprint_values(sprint))

    sp_tree = slide.shapes._spTree
    for frame in template.table_frames:
        sp_tree.remove(frame._element)

    fill_chart(template.chart_frame.chart, sprints, theme_colors)
    return leftover_tokens(slide)


def continuation_title(project_title: str, page: int) -> str:
    return project_title if page == 0 else f"{project_title}{CONTINUATION_SUFFIX}"
