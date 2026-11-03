"""Contents-page numbers and titles must jump to the track slide they name."""

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

from app.wsr_engine.index_updater import rebuild_index_from_projects
from app.wsr_engine.models import ProjectMap


def _add_run(paragraph, text: str, action: str | None = None):
    run = paragraph._p.makeelement(qn("a:r"), {})
    run_props = run.makeelement(qn("a:rPr"), {})
    if action is not None:
        link = run_props.makeelement(qn("a:hlinkClick"), {"action": action})
        link.set(qn("r:id"), "")
        run_props.append(link)
    run.append(run_props)
    text_elem = run.makeelement(qn("a:t"), {})
    text_elem.text = text
    run.append(text_elem)
    paragraph._p.append(run)


def _visible_run_links(cell, index_slide):
    links = []
    for paragraph in cell.text_frame._txBody.findall(qn("a:p")):
        for run in paragraph.findall(qn("a:r")):
            text_elem = run.find(qn("a:t"))
            text = "" if text_elem is None or not text_elem.text else text_elem.text
            if not text.strip():
                continue
            run_props = run.find(qn("a:rPr"))
            link = None if run_props is None else run_props.find(qn("a:hlinkClick"))
            target = None
            if link is not None and link.get(qn("r:id")):
                target = index_slide.part.rels[link.get(qn("r:id"))].target_part
            links.append((text, None if link is None else link.get("action"), target))
    return links


def test_contents_number_and_title_jump_to_the_track_slide():
    prs = Presentation()
    layout = prs.slide_layouts[5]
    prs.slides.add_slide(layout)
    index = prs.slides.add_slide(layout)
    target = prs.slides.add_slide(layout)

    title = index.shapes.add_textbox(Inches(0.2), Inches(0.2), Inches(2), Inches(0.3))
    title.text_frame.text = "Index"
    cell = index.shapes.add_table(
        1, 1, Inches(0.2), Inches(0.8), Inches(4), Inches(1)
    ).table.cell(0, 0)
    number = cell.text_frame.paragraphs[0]
    for child in list(number._p):
        if child.tag != qn("a:pPr"):
            number._p.remove(child)
    # The displayed number starts on a later run, and the column action is noaction.
    _add_run(number, "")
    _add_run(number, "0", "ppaction://noaction")
    _add_run(number, "7")
    label = cell.text_frame.add_paragraph()
    _add_run(label, "Pricing Core Service", "ppaction://noaction")

    updated = rebuild_index_from_projects(
        prs,
        [ProjectMap(project_name="RXD", main_slide_index=2)],
        {"RXD": "RXD"},
    )

    assert updated == 1
    links = _visible_run_links(cell, index)
    assert [item[0] for item in links] == ["03", "RXD"]
    assert all(action == "ppaction://hlinksldjump" for _text, action, _target in links)
    assert all(linked is target.part for _text, _action, linked in links)
    assert "ppaction://noaction" not in {
        link.get("action") for link in cell.text_frame._txBody.iter(qn("a:hlinkClick"))
    }


def test_contents_title_is_centered_under_its_number():
    prs = Presentation()
    layout = prs.slide_layouts[5]
    prs.slides.add_slide(layout)
    index = prs.slides.add_slide(layout)
    prs.slides.add_slide(layout)

    title = index.shapes.add_textbox(Inches(0.2), Inches(0.2), Inches(2), Inches(0.3))
    title.text_frame.text = "Index"
    cell = index.shapes.add_table(
        1, 1, Inches(0.2), Inches(0.8), Inches(4), Inches(1)
    ).table.cell(0, 0)
    number = cell.text_frame.paragraphs[0]
    for child in list(number._p):
        if child.tag != qn("a:pPr"):
            number._p.remove(child)
    number_props = number._p.makeelement(qn("a:pPr"), {"marL": "544195"})
    number._p.insert(0, number_props)
    _add_run(number, "07")
    label = cell.text_frame.add_paragraph()
    label_props = label._p.makeelement(qn("a:pPr"), {"marL": "509905"})
    label._p.insert(0, label_props)
    _add_run(label, "Pricing Core Service")

    rebuild_index_from_projects(
        prs,
        [ProjectMap(project_name="RXD", main_slide_index=2)],
        {"RXD": "RXD"},
    )

    visible = []
    for paragraph in cell.text_frame._txBody.findall(qn("a:p")):
        text = "".join(
            (node.text or "")
            for node in paragraph.findall(qn("a:r"))
            for node in [node.find(qn("a:t"))]
            if node is not None and node.text and node.text.strip()
        )
        if not text:
            continue
        props = paragraph.find(qn("a:pPr"))
        visible.append((text, None if props is None else props.get("algn"), None if props is None else props.get("marL")))

    assert visible == [("03", "ctr", None), ("RXD", "ctr", None)]
