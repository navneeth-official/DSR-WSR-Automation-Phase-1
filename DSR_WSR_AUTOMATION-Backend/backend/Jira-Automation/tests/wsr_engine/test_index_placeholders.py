"""Index slide: {Track Name} and {Slide Number} placeholders + slide jumps."""

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

from app.services.template_run_substitution import paragraph_plain_text
from app.wsr_engine.index_updater import fill_index_slide_track_placeholders
from app.wsr_engine.models import ProjectMap


def test_index_track_name_and_slide_number_placeholders():
    prs = Presentation()
    layout = prs.slide_layouts[5]
    prs.slides.add_slide(layout)
    index = prs.slides.add_slide(layout)
    prs.slides.add_slide(layout)
    prs.slides.add_slide(layout)

    index.shapes.add_textbox(Inches(0.2), Inches(0.2), Inches(2), Inches(0.3)).text_frame.text = "Index"
    table = index.shapes.add_table(2, 1, Inches(0.2), Inches(0.8), Inches(4), Inches(1.2)).table
    table.cell(0, 0).text = "{Slide Number}\n{Track Name}"
    table.cell(1, 0).text = "{Slide Number}\n{Track Name}"

    projects = [
        ProjectMap(project_name="PATRV", main_slide_index=1),
        ProjectMap(project_name="RXD", main_slide_index=2),
    ]
    updated = fill_index_slide_track_placeholders(
        prs,
        projects,
        {"PATRV": "Product Attribute", "RXD": "RXD Core"},
    )

    assert updated >= 2
    rows = [
        paragraph_plain_text(p)
        for p in table.cell(0, 0).text_frame._txBody.findall(qn("a:p"))
        if paragraph_plain_text(p).strip()
    ]
    body0 = " ".join(rows)
    assert "Product Attribute" in body0
    assert "02" in body0

    links = list(table.cell(0, 0).text_frame._txBody.iter(qn("a:hlinkClick")))
    assert links
    assert all(link.get("action") == "ppaction://hlinksldjump" for link in links)