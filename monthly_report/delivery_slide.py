"""Fill the Delivery Updates slide: sprint snapshot tables and status chart.

* Tables: ended layout has ``{{SC}}``; in-progress has ``{{RC}}``/``{{PC}}``.
* Chart: template series names, colours and legend are left unchanged. Only the
  number of category bars (sprints) and numeric values are updated. Each series is
  tied to a metric by the placeholders on that series in the template
  (e.g. ``{{CC}}``, ``{{SC}}`` on data labels), same keys as the tables.
"""

from __future__ import annotations

import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date

from lxml import etree
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.oxml.ns import qn
from pptx.shapes.graphfrm import GraphicFrame

from monthly_report.metrics import ENDED, IN_PROGRESS, SprintMetrics
from monthly_report.slide_ops import duplicate_slide
from monthly_report.tokens import (
    TOKEN_RE,
    DateValue,
    TokenValue,
    format_date,
    replace_tokens_in_shapes,
    replace_tokens_in_text_frame,
    token_key,
    tokens_in_shapes,
)

ENDED_TABLE = "ended"
IN_PROGRESS_TABLE = "in_progress"

SCHEDULE_DATE_FORMAT = "MMM DD"
SPILL_OVER_SERIES = "Spill Over"

METRIC_KEYS = frozenset({"tc", "cc", "rc", "pc", "sc"})
_SPRINT_KEYS = METRIC_KEYS | {"sprint_name", "status", "start_date", "end_date", "start", "end"}
_KIND_NAME_RE = re.compile(r"\((ended|in_progress)\)\s*$")


def format_schedule_date(value: date) -> str:
    return format_date(value, SCHEDULE_DATE_FORMAT)


def continuation_suffix() -> str:
    return os.environ.get("MSR_CONTINUATION_SUFFIX", " (Contd.)")


def status_label(status: str) -> str:
    """Text written into ``{{Status}}``; override per deck via environment."""
    if status == ENDED:
        return os.environ.get("MSR_STATUS_ENDED_LABEL", "").strip() or ENDED
    if status == IN_PROGRESS:
        return os.environ.get("MSR_STATUS_IN_PROGRESS_LABEL", "").strip() or IN_PROGRESS
    return status


def _normalize_label(text: str) -> str:
    return re.sub(r"[\s_\-–—]+", " ", (text or "").strip().lower())


def _is_table(shape) -> bool:
    return bool(getattr(shape, "has_table", False) and shape.has_table)


def _is_chart(shape) -> bool:
    return bool(getattr(shape, "has_chart", False) and shape.has_chart)


def _table_token_keys(frame) -> set[str]:
    keys: set[str] = set()
    for row in frame.table.rows:
        for cell in row.cells:
            for raw in TOKEN_RE.findall(cell.text or ""):
                keys.add(token_key(raw))
    return keys


def table_kind(frame) -> str | None:
    """Ended / in-progress sprint layout, from placeholders (or our marker once filled)."""
    if not _is_table(frame):
        return None
    tokens = _table_token_keys(frame)
    if "sc" in tokens:
        return ENDED_TABLE
    if tokens & {"rc", "pc"}:
        return IN_PROGRESS_TABLE
    if tokens & _SPRINT_KEYS:
        return IN_PROGRESS_TABLE
    marker = _KIND_NAME_RE.search(frame.name or "")
    return marker.group(1) if marker else None


def column_labels(frame) -> dict[str, str]:
    """``{token_key: header text}`` for cells holding a single placeholder."""
    table = frame.table
    labels: dict[str, str] = {}
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row.cells):
            text = (cell.text or "").strip()
            match = TOKEN_RE.fullmatch(text)
            if match is None:
                continue
            key = token_key(match.group(1))
            for above in range(r - 1, -1, -1):
                header = (table.cell(above, c).text or "").strip()
                if header and not TOKEN_RE.search(header):
                    labels.setdefault(key, header)
                    break
    return labels


_CHART_PAD_CATEGORY = "\u00a0"


@dataclass
class DeliveryTemplate:
    chart_frame: GraphicFrame
    ended_table: GraphicFrame
    in_progress_table: GraphicFrame
    table_frames: list[GraphicFrame]
    slots: list[tuple[int, int]]
    series_styles: dict[str, etree._Element]
    metric_labels: dict[str, str] = field(default_factory=dict)
    chart_gap_width: int | None = None
    chart_overlap: int | None = None

    @property
    def sprints_per_slide(self) -> int:
        return len(self.slots)

    def prototype_for(self, sprint: SprintMetrics) -> GraphicFrame:
        return self.ended_table if sprint.is_ended else self.in_progress_table

    @property
    def spill_series_label(self) -> str:
        return self.metric_labels.get("sc") or SPILL_OVER_SERIES


def is_delivery_slide(slide) -> bool:
    shapes = list(slide.shapes)
    return any(_is_chart(s) for s in shapes) and any(table_kind(s) for s in shapes)


def find_delivery_slide(prs):
    for slide in prs.slides:
        if is_delivery_slide(slide):
            return slide
    raise ValueError(
        "No Delivery Updates slide in template: need a chart plus a table with sprint "
        "placeholders ({{TC}}, {{CC}}, {{SC}} / {{RC}}, {{PC}} ...)"
    )


def analyze_delivery_slide(slide) -> DeliveryTemplate:
    shapes = list(slide.shapes)
    tables = sorted((s for s in shapes if table_kind(s)), key=lambda s: (s.top, s.left))
    if not tables:
        raise ValueError("Delivery slide has no sprint table placeholders")
    ended = next((t for t in tables if table_kind(t) == ENDED_TABLE), None)
    in_progress = next((t for t in tables if table_kind(t) == IN_PROGRESS_TABLE), None)
    chart_frame = next((s for s in shapes if _is_chart(s)), None)
    if chart_frame is None:
        raise ValueError("Delivery slide has no chart")

    labels: dict[str, str] = {}
    for frame in (ended, in_progress):
        if frame is not None:
            for key, label in column_labels(frame).items():
                labels.setdefault(key, label)

    plot = chart_frame.chart.plots[0]
    return DeliveryTemplate(
        chart_frame=chart_frame,
        ended_table=ended or in_progress,
        in_progress_table=in_progress or ended,
        table_frames=tables,
        slots=[(t.left, t.top) for t in tables],
        series_styles=_capture_series_styles(chart_frame.chart),
        metric_labels=labels,
        chart_gap_width=plot.gap_width,
        chart_overlap=getattr(plot, "overlap", None),
    )


def duplicate_delivery_slide(prs, source, template: DeliveryTemplate):
    """
    Copy the delivery slide without PowerPoint.

    The chart is recreated with ``add_chart`` (copying the chart XML duplicates
    workbook parts and corrupts the .pptx). Template series fills are restored
    in ``fill_chart`` via ``series_styles``.
    """
    new_slide = duplicate_slide(
        prs, source, skip_shape_ids=frozenset({template.chart_frame.shape_id})
    )
    _clone_chart(template.chart_frame, new_slide)
    return new_slide


def _clone_chart(source_frame: GraphicFrame, slide) -> GraphicFrame:
    source = source_frame.chart
    placeholder = CategoryChartData()
    placeholder.categories = ["-"]
    for series in source.plots[0].series:
        placeholder.add_series(series.name, [0])
    try:
        chart_type = source.chart_type
    except (KeyError, ValueError, NotImplementedError):
        chart_type = XL_CHART_TYPE.COLUMN_STACKED
    frame = slide.shapes.add_chart(
        chart_type,
        source_frame.left,
        source_frame.top,
        source_frame.width,
        source_frame.height,
        placeholder,
    )
    frame.name = source_frame.name
    return frame


def _series_key(name: str) -> str:
    return _normalize_label(name).replace(" ", "_")


def _capture_series_styles(chart) -> dict[str, etree._Element]:
    """Copy each series' shape properties (solid, RGB, theme or gradient fill)."""
    styles: dict[str, etree._Element] = {}
    for series in chart.plots[0].series:
        sp_pr = series._element.find(qn("c:spPr"))
        if sp_pr is not None:
            styles[_series_key(series.name)] = deepcopy(sp_pr)
    return styles


def _apply_series_styles(chart, styles: dict[str, etree._Element]) -> None:
    for series in chart.plots[0].series:
        saved = styles.get(_series_key(series.name))
        if saved is None:
            continue
        current = series._element.get_or_add_spPr()
        current.getparent().replace(current, deepcopy(saved))


def _metric_tokens_on_series(series) -> list[str]:
    """All ``{{CC}}`` / ``{{RC}}`` / … keys on a series (data labels may mix tokens across points)."""
    keys: list[str] = []
    for el in series._element.iter():
        text = el.text or ""
        if not text:
            continue
        for raw in TOKEN_RE.findall(text):
            key = token_key(raw)
            if key in METRIC_KEYS:
                keys.append(key)
    return keys


def _series_metric_fallback(name: str, metric_labels: dict[str, str]) -> str | None:
    """Map a series title to a metric key (series name ~ table header, or ``{{RC}}``-style name)."""
    stripped = (name or "").strip()
    placeholder = TOKEN_RE.fullmatch(stripped)
    if placeholder:
        key = token_key(placeholder.group(1))
        return key if key in METRIC_KEYS else None
    direct = token_key(stripped)
    if direct in METRIC_KEYS:
        return direct
    normalized = _normalize_label(stripped)
    for key, label in metric_labels.items():
        if _normalize_label(label) == normalized:
            return key
    # Built-in aliases so future templates still resolve without perfect header text.
    aliases = {
        "completed": "cc",
        "in review": "rc",
        "in progress": "pc",
        "spill over": "sc",
        "carry over": "sc",
    }
    return aliases.get(normalized)


def _resolve_series_metric(
    series,
    name: str,
    metric_labels: dict[str, str],
) -> str | None:
    """
    Pick the metric for one chart series.

    Prefer the series title / table-header match over data-label tokens. Templates often
    copy-paste labels across points (e.g. ``{{SC}}`` then ``{{RC}}`` on \"In-Review\"), and
    taking the first token alone maps the wrong values into the bar.
    """
    name_metric = _series_metric_fallback(name, metric_labels)
    if name_metric:
        return name_metric

    tokens = _metric_tokens_on_series(series)
    if not tokens:
        return None
    # Majority among label tokens when the series name is not informative.
    counts: dict[str, int] = {}
    for key in tokens:
        counts[key] = counts.get(key, 0) + 1
    return max(counts.items(), key=lambda item: (item[1], -tokens.index(item[0])))[0]


def _series_metrics_for_chart(
    chart,
    names: list[str],
    metric_labels: dict[str, str],
) -> list[str | None]:
    return [
        _resolve_series_metric(series, name, metric_labels)
        for series, name in zip(chart.plots[0].series, names)
    ]


def _pad_chart_categories(
    sprints: list[SprintMetrics],
    slots: int,
) -> tuple[list[SprintMetrics | None], list[str]]:
    """
    Keep one column per template slot so bar width matches the master layout.

    Unused slots get blank category labels and no stacked values (same geometry as a
    full slide with fewer sprints filled).
    """
    slots = max(1, slots)
    padded: list[SprintMetrics | None] = list(sprints)
    categories = [sprint.sprint_name for sprint in sprints]
    while len(padded) < slots:
        padded.append(None)
        categories.append(_CHART_PAD_CATEGORY)
    return padded, categories


def _apply_chart_layout(chart, template: DeliveryTemplate) -> None:
    """Restore template gap/overlap after ``replace_data`` (especially on cloned charts)."""
    plot = chart.plots[0]
    if template.chart_gap_width is not None:
        plot.gap_width = template.chart_gap_width
    if template.chart_overlap is not None:
        plot.overlap = template.chart_overlap


def _chart_point_value(
    sprint: SprintMetrics | None,
    metric: str | None,
    *,
    has_spill_series: bool = False,
) -> float | None:
    """
    Stacked charts use ``None`` for a missing segment so no sliver or ``0`` label shows.

    When the template has a spill / carry-over series, ended sprints show unfinished work
    only there (same as the ended table). In-review / in-progress segments are reserved
    for in-progress sprints so bars never double-count spill + RC/PC.
    """
    if sprint is None or not metric:
        return None
    if metric == "sc":
        amount = sprint.spill_over
    elif metric in {"rc", "pc"} and sprint.is_ended and has_spill_series:
        amount = None
    else:
        amount = {
            "tc": sprint.total,
            "cc": sprint.completed,
            "rc": sprint.in_review,
            "pc": sprint.in_progress,
        }.get(metric, 0)
    if not amount:
        return None
    return float(amount)


def _chart_label_values_for(sprint: SprintMetrics, metric: str | None, value: float) -> dict[str, str]:
    """Only the active metric is non-empty so other placeholders on the label stay blank."""
    labels = {key: "" for key in METRIC_KEYS}
    labels["sprint_name"] = sprint.sprint_name
    labels["sprint"] = sprint.sprint_name
    if metric:
        labels[metric] = str(int(value))
    return labels


def _clear_data_label_text(label) -> None:
    if not getattr(label, "has_text_frame", False) or not label.has_text_frame:
        return
    for paragraph in label.text_frame.paragraphs:
        if paragraph.runs:
            paragraph.runs[0].text = ""
            for run in paragraph.runs[1:]:
                run.text = ""
        else:
            paragraph.text = ""


def sprint_values(sprint: SprintMetrics) -> dict[str, TokenValue]:
    start = DateValue(sprint.start_date, SCHEDULE_DATE_FORMAT)
    end = DateValue(sprint.end_date, SCHEDULE_DATE_FORMAT)
    return {
        "sprint_name": sprint.sprint_name,
        "sprint": sprint.sprint_name,
        "start_date": start,
        "end_date": end,
        "start": start,
        "end": end,
        "status": status_label(sprint.status),
        "tc": str(sprint.total),
        "cc": str(sprint.completed),
        "rc": str(sprint.in_review),
        "pc": str(sprint.in_progress),
        "sc": str(sprint.spill_over) if sprint.spill_over is not None else "",
    }


def _place_sprint_table(
    slide,
    prototype: GraphicFrame,
    slot: tuple[int, int],
    shape_id: int,
    name: str,
) -> GraphicFrame:
    element = deepcopy(prototype._element)
    c_nv_pr = element.nvGraphicFramePr.cNvPr
    c_nv_pr.id = shape_id
    c_nv_pr.name = name
    slide.shapes._spTree.insert_element_before(element, "p:extLst")
    frame = GraphicFrame(element, slide.shapes)
    frame.left, frame.top = slot
    return frame


def _fill_table(frame: GraphicFrame, values: dict[str, TokenValue]) -> None:
    for row in frame.table.rows:
        for cell in row.cells:
            replace_tokens_in_text_frame(cell.text_frame, values)


def _detach_linked_workbook(chart) -> None:
    """Drop a link to an external workbook so replace_data embeds the data in the deck."""
    external_data = chart._chartSpace.find(qn("c:externalData"))
    if external_data is None:
        return
    r_id = external_data.get(qn("r:id"))
    if chart.part.rels[r_id].is_external:
        chart._chartSpace.remove(external_data)
        chart.part.drop_rel(r_id)


def _fill_chart_label_placeholders(
    chart,
    sprints: list[SprintMetrics | None],
    metrics: list[str | None],
    *,
    has_spill_series: bool,
) -> None:
    """Replace ``{{CC}}`` / ``{{SC}}`` / … on chart data labels; hide labels when value is 0."""
    plot = chart.plots[0]
    for si, series in enumerate(plot.series):
        metric = metrics[si] if si < len(metrics) else None
        for pi, sprint in enumerate(sprints):
            if pi >= len(series.points):
                break
            try:
                label = series.points[pi].data_label
            except (AttributeError, ValueError):
                continue
            if not getattr(label, "has_text_frame", False) or not label.has_text_frame:
                continue
            value = _chart_point_value(
                sprint, metric, has_spill_series=has_spill_series
            )
            if value is None or sprint is None:
                _clear_data_label_text(label)
                continue
            replace_tokens_in_text_frame(
                label.text_frame,
                _chart_label_values_for(sprint, metric, value),
            )


def fill_chart(
    chart,
    sprints: list[SprintMetrics],
    template: DeliveryTemplate,
    series_styles: dict[str, etree._Element] | None = None,
) -> None:
    """
    One bar per sprint; each template series keeps its name and style.

    Values match the tables: ended bars use completed + spill/carry-over; in-progress
    bars use completed + in-review + in-progress.
    """
    styles = series_styles if series_styles is not None else template.series_styles
    plot = chart.plots[0]
    names = [series.name for series in plot.series]
    metrics = _series_metrics_for_chart(chart, names, template.metric_labels)
    has_spill_series = "sc" in {m for m in metrics if m}
    padded_sprints, categories = _pad_chart_categories(
        sprints, template.sprints_per_slide
    )

    data = CategoryChartData()
    data.categories = categories
    for name, metric in zip(names, metrics):
        data.add_series(
            name,
            [
                _chart_point_value(sprint, metric, has_spill_series=has_spill_series)
                for sprint in padded_sprints
            ],
        )

    _detach_linked_workbook(chart)
    chart.replace_data(data)
    _apply_chart_layout(chart, template)
    if styles:
        _apply_series_styles(chart, styles)
    _fill_chart_label_placeholders(
        chart, padded_sprints, metrics, has_spill_series=has_spill_series
    )


def leftover_tokens(slide) -> list[str]:
    return tokens_in_shapes(slide.shapes)


def fill_delivery_slide(
    slide,
    project_title: str,
    sprints: list[SprintMetrics],
    *,
    series_styles: dict[str, etree._Element] | None = None,
    extra_values: dict[str, TokenValue] | None = None,
) -> list[str]:
    """Fill one delivery slide with up to ``sprints_per_slide`` sprints; return leftover tokens."""
    template = analyze_delivery_slide(slide)
    if len(sprints) > template.sprints_per_slide:
        raise ValueError(
            f"{len(sprints)} sprints given; slide holds {template.sprints_per_slide}"
        )

    sprint_elements = [frame._element for frame in template.table_frames]
    slide_values: dict[str, TokenValue] = {**(extra_values or {}), "project_name": project_title}
    non_sprint_shapes = [
        s for s in slide.shapes if not any(s._element is e for e in sprint_elements)
    ]
    replace_tokens_in_shapes(non_sprint_shapes, slide_values)

    next_id = max(shape.shape_id for shape in slide.shapes) + 1
    for position, sprint in enumerate(sprints):
        prototype = template.prototype_for(sprint)
        kind = ENDED_TABLE if sprint.is_ended else IN_PROGRESS_TABLE
        frame = _place_sprint_table(
            slide,
            prototype,
            template.slots[position],
            next_id + position,
            f"Sprint Table {position + 1} ({kind})",
        )
        _fill_table(frame, {**slide_values, **sprint_values(sprint)})

    sp_tree = slide.shapes._spTree
    for frame in template.table_frames:
        sp_tree.remove(frame._element)

    fill_chart(template.chart_frame.chart, sprints, template, series_styles)
    return leftover_tokens(slide)


def continuation_title(project_title: str, page: int) -> str:
    return project_title if page == 0 else f"{project_title}{continuation_suffix()}"
