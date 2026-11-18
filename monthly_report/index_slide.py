"""Index slide for the monthly cadence deck (layout matches the weekly WSR index)."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from rapidfuzz import fuzz

from monthly_report.index_layout import INDEX_ENTRY_RULES, IndexLayout, discover_index_layout

_INDEX_NUMBER_RE = re.compile(r"^\d{1,2}\u200b?$")

_DELIVERY_INDEX_KEYWORDS = tuple(
    needles[0]
    for needles, _title, is_delivery in INDEX_ENTRY_RULES
    if is_delivery
)


def normalize_title_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u200b", "")).strip()


def slide_title_text(slide) -> str:
    if slide.shapes.title and slide.shapes.title.text:
        return slide.shapes.title.text
    return ""


@dataclass(frozen=True)
class IndexProject:
    """Maps a deck project to the first slide of its Delivery Updates section."""

    project_name: str
    main_slide_index: int


def find_index_slide_index(prs: Presentation) -> int | None:
    for index, slide in enumerate(prs.slides):
        if normalize_title_text(slide_title_text(slide)).lower() == "index":
            return index
        for shape in slide.shapes:
            if shape.has_text_frame and normalize_title_text(shape.text_frame.text).lower() == "index":
                return index
        if find_index_table(slide) is not None and normalize_title_text(slide_title_text(slide)):
            if "index" in normalize_title_text(slide_title_text(slide)).lower():
                return index
    return None


def find_index_table(slide):
    for shape in slide.shapes:
        if shape.has_table:
            return shape.table
    return None


def insert_index_slide(
    monthly_prs: Presentation,
    reference_prs: Presentation,
    *,
    insert_after_cover: int = 1,
) -> tuple[object, IndexLayout]:
    """Copy the Index slide from the WSR reference deck into the monthly deck."""
    ref_index = find_index_slide_index(reference_prs)
    if ref_index is None:
        raise ValueError("Index slide not found in reference template")
    from monthly_report.slide_ops import import_slide_from_presentation

    index_slide = import_slide_from_presentation(
        monthly_prs,
        reference_prs,
        ref_index,
        insert_index=insert_after_cover,
    )
    table = find_index_table(index_slide)
    if table is None:
        raise ValueError("Index table not found on reference Index slide")
    layout = discover_index_layout(table)
    layout.column_prototypes = capture_column_prototypes(table, layout)
    return index_slide, layout


def capture_column_prototypes(table, layout: IndexLayout) -> dict[int, object]:
    prototypes: dict[int, object] = {}
    for slot in sorted(layout.slots, key=lambda item: (item.row, item.col)):
        if slot.col in prototypes:
            continue
        prototypes[slot.col] = copy.deepcopy(table.cell(slot.row, slot.col).text_frame._txBody)
    return prototypes


def _is_index_number_paragraph(paragraph) -> bool:
    text = normalize_title_text("".join(run.text for run in paragraph.runs))
    return bool(_INDEX_NUMBER_RE.match(text))


def _set_paragraph_slide_number(paragraph, slide_number: int) -> None:
    display = f"{slide_number:02d}"
    if paragraph.runs:
        paragraph.runs[0].text = display
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run().text = display


def _set_index_cell_content(cell, slide_number: int, label: str) -> None:
    has_number = any(_is_index_number_paragraph(p) for p in cell.text_frame.paragraphs)
    if not has_number and cell.text_frame.paragraphs:
        _set_paragraph_slide_number(cell.text_frame.paragraphs[0], slide_number)

    label_written = False
    for paragraph in cell.text_frame.paragraphs:
        if _is_index_number_paragraph(paragraph):
            _set_paragraph_slide_number(paragraph, slide_number)
            continue
        if not label_written:
            if paragraph.runs:
                paragraph.runs[0].text = label
                for run in paragraph.runs[1:]:
                    run.text = ""
            else:
                paragraph.add_run().text = label
            label_written = True
        else:
            for run in paragraph.runs:
                run.text = ""


def _set_element_hyperlink_to_slide(hlink_elem, index_slide, target_slide_idx, prs) -> None:
    target_part = prs.slides[target_slide_idx].part
    slide_rid = index_slide.part.relate_to(target_part, RT.SLIDE)
    hlink_elem.set(qn("r:id"), slide_rid)


def _update_cell_index_entry(cell, index_slide, target_slide_idx, prs) -> None:
    display_num = target_slide_idx + 1
    for paragraph in cell.text_frame.paragraphs:
        if _is_index_number_paragraph(paragraph):
            _set_paragraph_slide_number(paragraph, display_num)

    for p_elem in cell.text_frame._txBody.findall(qn("a:p")):
        for hlink in p_elem.iter(qn("a:hlinkClick")):
            _set_element_hyperlink_to_slide(hlink, index_slide, target_slide_idx, prs)


def _normalize_index_text(text: str) -> str:
    return normalize_title_text(text).lower()


def _unique_table_cells(table):
    """Merged cells appear once per row; dedupe by underlying ``_tc``."""
    seen: set[int] = set()
    cells = []
    for row in table.rows:
        for cell in row.cells:
            key = id(cell._tc)
            if key in seen:
                continue
            seen.add(key)
            cells.append(cell)
    return cells


def _cell_has_delivery_keyword(cell) -> bool:
    text = _normalize_index_text(cell.text_frame.text)
    return any(keyword in text for keyword in _DELIVERY_INDEX_KEYWORDS)


def _cell_has_index_content(cell) -> bool:
    text = _normalize_index_text(cell.text_frame.text)
    if not text:
        return False
    if _cell_has_delivery_keyword(cell):
        return True
    if "matters of attention" in text or "team allocation" in text:
        return True
    for paragraph in cell.text_frame.paragraphs:
        if _is_index_number_paragraph(paragraph):
            return True
    return False


def _clear_index_cell(cell) -> None:
    for paragraph in cell.text_frame.paragraphs:
        for run in paragraph.runs:
            run.text = ""
    for p_elem in cell.text_frame._txBody.findall(qn("a:p")):
        for hlink in list(p_elem.findall(qn("a:hlinkClick"))):
            p_elem.remove(hlink)


def _clone_cell_text_body(dst_cell, src_tx_body) -> None:
    dst_tc = dst_cell._tc
    old_tx = dst_tc.find(qn("a:txBody"))
    if old_tx is not None:
        dst_tc.remove(old_tx)
    dst_tc.insert(0, copy.deepcopy(src_tx_body))


def _index_cell_at(table, row: int, col: int):
    if row < 0 or col < 0 or row >= len(table.rows):
        return None
    if col >= len(table.columns):
        return None
    return table.cell(row, col)


def _match_project_for_index(projects: list[IndexProject], search_title: str) -> IndexProject | None:
    needle = search_title.lower()
    if needle == "loco":
        for project in projects:
            name = project.project_name.lower()
            if "loco" in name and "location core" not in name:
                return project
        return None

    best: IndexProject | None = None
    best_score = 0
    for project in projects:
        name = project.project_name.lower()
        if needle == "location core service" and "loco" in name and "location core" not in name:
            continue
        score = fuzz.partial_ratio(needle, name)
        if score > best_score and score >= 85:
            best_score = score
            best = project
    return best


def collect_monthly_index_entries(
    projects: list[IndexProject],
    content_labels: dict[str, str],
) -> list[tuple[int, str]]:
    """
    One row per project in deck order (ascending delivery slide index).

    Unlike the weekly WSR index, monthly cadence does not preserve fixed template
    slot positions per service — entries compact into the grid left-to-right, top-to-bottom.
    """
    ordered = sorted(projects, key=lambda project: project.main_slide_index)
    entries: list[tuple[int, str]] = []
    seen_slides: set[int] = set()
    seen_labels: set[str] = set()
    for project in ordered:
        if project.main_slide_index in seen_slides:
            continue
        label = content_labels.get(project.project_name, project.project_name)
        label_key = label.strip().lower()
        if label_key in seen_labels:
            continue
        seen_slides.add(project.main_slide_index)
        seen_labels.add(label_key)
        entries.append((project.main_slide_index, label))
    return entries


def index_entries_for_track_names(
    track_names: list[str],
    projects: list[IndexProject],
    content_labels: dict[str, str],
) -> list[tuple[int, str]]:
    """
    One index row per included project, unless multiple track names were given — then
    only the first track name appears (slides still exist for every selected project).
    """
    if not projects:
        return []
    if len(track_names) > 1:
        first_slide = min(project.main_slide_index for project in projects)
        return [(first_slide, track_names[0].strip())]
    return collect_monthly_index_entries(projects, content_labels)


def rebuild_index(
    prs: Presentation,
    projects: list[IndexProject],
    layout: IndexLayout,
    content_labels: dict[str, str] | None = None,
    track_names: list[str] | None = None,
) -> int:
    """Write project names and slide numbers into the Index table."""
    index_idx = find_index_slide_index(prs)
    if index_idx is None:
        return 0

    index_slide = prs.slides[index_idx]
    table = find_index_table(index_slide)
    if table is None:
        return 0

    content_labels = content_labels or {}
    track_names = track_names or []
    entries = index_entries_for_track_names(track_names, projects, content_labels)
    if not entries:
        return 0

    for cell in _unique_table_cells(table):
        if _cell_has_index_content(cell):
            _clear_index_cell(cell)

    rows = len(table.rows)
    cols = len(table.columns)
    positions = layout.grid_positions(rows, cols)[: len(entries)]

    updated = 0
    for (target_idx, label), (row, col) in zip(entries, positions):
        cell = _index_cell_at(table, row, col)
        if cell is None:
            continue
        proto = layout.column_prototypes.get(col)
        if proto is not None:
            _clone_cell_text_body(cell, proto)
        _set_index_cell_content(cell, target_idx + 1, label)
        _update_cell_index_entry(cell, index_slide, target_idx, prs)
        updated += 1
    return updated
