from pptx import Presentation
from pptx.oxml.ns import qn

path = "output/monthly/HEB_MSR_stress_full.pptx"
prs = Presentation(path)
for si in [3, 5]:
    slide = prs.slides[si - 1]
    chart = next(s for s in slide.shapes if s.has_chart).chart
    print("slide", si, slide.shapes.title.text)
    for ser in chart.plots[0].series:
        cat = ser._element.find(qn("c:cat"))
        if cat is None:
            continue
        for ref in cat.iter(qn("c:strRef")):
            f = ref.find(qn("c:f"))
            print(" ", ser.name, "cat f=", None if f is None else f.text)
        for ref in ser._element.find(qn("c:val")).iter(qn("c:numRef")):
            f = ref.find(qn("c:f"))
            print(" ", ser.name, "val f=", None if f is None else f.text)
