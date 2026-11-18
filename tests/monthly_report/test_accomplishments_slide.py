from pptx import Presentation

from monthly_report.accomplishments_slide import fill_accomplishments_slide, is_accomplishments_slide
from monthly_report.accomplishments_summarizer import AccomplishmentsSummary
from monthly_report.config import resolve_template


def test_accomplishments_use_separate_paragraphs_with_template_style():
    template = resolve_template()
    prs = Presentation(str(template))
    slide = next(s for s in prs.slides if is_accomplishments_slide(s))
    fill_accomplishments_slide(
        slide,
        project_title="Supplier Core",
        summary=AccomplishmentsSummary(
            completed=(
                "Implemented GIIN validation endpoint",
                "Fixed GCP bucket name mismatch in prod API configurations",
            ),
            in_progress=("Initiated automation of the Partner SIDM application",),
        ),
        max_lines=6,
    )
    body = None
    for shape in slide.shapes:
        if shape.has_table and "accomplishment" in shape.table.cell(0, 0).text.lower():
            body = shape.table.cell(1, 0).text_frame
    assert body is not None
    assert len([p for p in body.paragraphs if p.text.strip()]) == 3
    joined = body.text
    assert "Implemented GIIN" in joined
    assert "(In progress)" not in joined
    sizes = {
        run.font.size.pt
        for paragraph in body.paragraphs
        if paragraph.text.strip()
        for run in paragraph.runs
        if run.text.strip() and run.font.size
    }
    assert len(sizes) == 1
