"""Static-label index must rebuild from projects — never in-place fuzzy patch."""

from __future__ import annotations

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

from app.services.ppt_shape_utils import normalize_title_text
from app.wsr_engine.index_updater import (
    fill_index_slide_track_placeholders,
    rebuild_index_from_projects,
)
from app.wsr_engine.models import ProjectMap, TemplateModel
from app.wsr_engine.ppt_writer import PptWriter


def _cell_blob(cell) -> str:
    return normalize_title_text(cell.text_frame.text)


def _build_static_heb_index() -> tuple[Presentation, object]:
    """Mimic Generic Template index: static labels, no {Track Name} placeholders."""
    prs = Presentation()
    layout = prs.slide_layouts[5]
    prs.slides.add_slide(layout)  # cover
    index = prs.slides.add_slide(layout)
    # Delivery targets that exist in this run
    prs.slides.add_slide(layout)  # Cost Core -> 03
    prs.slides.add_slide(layout)  # Supplier Core -> 04
    prs.slides.add_slide(layout)  # Matters
    prs.slides.add_slide(layout)  # Team Allocation

    title = index.shapes.add_textbox(Inches(0.2), Inches(0.2), Inches(2), Inches(0.3))
    title.text_frame.text = "Index"
    table = index.shapes.add_table(3, 3, Inches(0.2), Inches(0.8), Inches(8), Inches(3)).table
    table.cell(0, 0).text = "03\nCost Core Service\nCHEDR (Haskell)"
    table.cell(0, 1).text = "08\nSupplier Core Service\nQA and SPUR (Haskell)"
    table.cell(0, 2).text = "03\nPricing Core Service\n(Haskell and Java)"
    table.cell(1, 0).text = "08\nWentworth\n(Haskell)"
    table.cell(1, 1).text = "03\nLocation Core Service\n(Java and Angular)"
    table.cell(1, 2).text = "10\nPharmacy and Wellness\n(QA)"
    table.cell(2, 2).text = "11\nMatters of Attention"
    return prs, table


def test_static_index_fill_returns_zero_so_rebuild_can_run():
    prs, _table = _build_static_heb_index()
    projects = [
        ProjectMap(project_name="CCS", main_slide_index=2),
        ProjectMap(project_name="SCS", main_slide_index=3),
    ]
    assert (
        fill_index_slide_track_placeholders(
            prs,
            projects,
            {"CCS": "Cost Core Service", "SCS": "Supplier Core Service"},
        )
        == 0
    )


def test_static_index_rebuild_drops_unmatched_template_tracks():
    prs, table = _build_static_heb_index()
    projects = [
        ProjectMap(project_name="CCS", main_slide_index=2),
        ProjectMap(project_name="SCS", main_slide_index=3),
    ]
    labels = {"CCS": "Cost Core Service", "SCS": "Supplier Core Service"}
    updated = rebuild_index_from_projects(prs, projects, labels)
    assert updated >= 2

    blobs = [
        _cell_blob(table.cell(r, c))
        for r in range(len(table.rows))
        for c in range(len(table.columns))
        if _cell_blob(table.cell(r, c)).strip()
    ]
    joined = " | ".join(blobs)
    assert "Cost Core Service" in joined
    assert "Supplier Core Service" in joined
    assert "Pricing Core" not in joined
    assert "Location Core" not in joined
    assert "Wentworth" not in joined

    # Numbers must match the actual main slides (02-index → 03 display).
    assert any(b.startswith("03") and "Cost Core" in b for b in blobs)
    assert any(b.startswith("04") and "Supplier Core" in b for b in blobs)
    # Never leave multiple cells pointing at Cost Core as "03".
    assert sum(1 for b in blobs if b.startswith("03")) == 1


def test_update_index_never_patches_static_template_in_place():
    """Regression: fill must not short-circuit rebuild for static HEB index labels."""
    prs, table = _build_static_heb_index()
    writer = object.__new__(PptWriter)
    writer.prs = prs
    writer.template_model = TemplateModel(template_path="dummy.pptx", index_layout=None)

    projects = [
        ProjectMap(project_name="CCS", main_slide_index=2),
        ProjectMap(project_name="SCS", main_slide_index=3),
    ]
    labels = {"CCS": "Cost Core Service", "SCS": "Supplier Core Service"}
    updated = writer.update_index(projects, skeleton_mode=True, content_labels=labels)
    assert updated >= 2

    blobs = [
        _cell_blob(table.cell(r, c))
        for r in range(len(table.rows))
        for c in range(len(table.columns))
        if _cell_blob(table.cell(r, c)).strip()
    ]
    assert not any("Pricing Core" in b for b in blobs)
    assert sum(1 for b in blobs if b.startswith("03")) == 1

    # Hyperlink on Cost Core cell must target slide index 2.
    cost_cell = next(
        table.cell(r, c)
        for r in range(len(table.rows))
        for c in range(len(table.columns))
        if "Cost Core" in _cell_blob(table.cell(r, c))
    )
    index_slide = prs.slides[1]
    targets = []
    for link in cost_cell.text_frame._txBody.iter(qn("a:hlinkClick")):
        rid = link.get(qn("r:id"))
        if rid:
            targets.append(index_slide.part.rels[rid].target_part)
    assert targets
    assert all(t is prs.slides[2].part for t in targets)
