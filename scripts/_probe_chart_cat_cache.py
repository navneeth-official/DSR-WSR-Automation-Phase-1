from pptx import Presentation
from pptx.oxml.ns import qn

for path, slides in [
    ("templates/monthly/G10X_H-E-B_Pricing cadence Meeting Template.pptx", [3]),
    ("output/monthly/HEB_MSR_stress_full.pptx", [3, 5, 7]),
]:
    prs = Presentation(path)
    for si in slides:
        slide = prs.slides[si - 1]
        title = slide.shapes.title.text if slide.shapes.title else ""
        chart = next(s for s in slide.shapes if s.has_chart).chart
        plot = chart.plots[0]
        print(f"\n{path} slide {si}: {title[:50]}")
        print("  categories", list(plot.categories))
        print("  grouping", plot._element.find(qn("c:grouping")).get("val"))
        print("  gap", plot.gap_width, "overlap", getattr(plot, "overlap", "?"))
        root = chart._element
        for cat in root.iter(qn("c:cat")):
            for lit in cat.iter(qn("c:strCache")):
                pts = lit.findall(qn("c:pt"))
                print("  strCache pts", len(pts), [p.find(qn("c:v")).text for p in pts])
            for lit in cat.iter(qn("c:strRef")):
                f = lit.find(qn("c:f"))
                cache = lit.find(qn("c:strCache"))
                if cache is not None:
                    pts = cache.findall(qn("c:pt"))
                    print("  strRef cache pts", len(pts))
