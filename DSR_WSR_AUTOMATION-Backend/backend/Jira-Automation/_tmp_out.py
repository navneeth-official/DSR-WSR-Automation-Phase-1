from pptx import Presentation
from pptx.oxml.ns import qn

src = r"C:\Users\AmithKrishnan(G1)XIN\Downloads\G10X H-E-B WSR Sustainment 05 June 2026  Generic Template.pptx"
prs = Presentation(src)
print("TEMPLATE")
for i, slide in enumerate(prs.slides):
    titles = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False) and "delivery" in shape.text_frame.text.lower():
            titles.append(shape.text_frame.text.strip()[:80])
    print(i, titles or "(no delivery title)")

out = Presentation(r"C:\Users\AmithKrishnan(G1)XIN\Downloads\HEB_Delivery_Status_placeholders.pptx")
slide = out.slides[8]
print("\nWENTWORTH TABLES")
for si, shape in enumerate(slide.shapes):
    if not getattr(shape, "has_table", False):
        continue
    print(f"shape {si} {shape.name} {len(shape.table.rows)}x{len(shape.table.columns)}")
    for ri, row in enumerate(shape.table.rows):
        for ci, cell in enumerate(row.cells):
            paras = cell.text_frame._txBody.findall(qn("a:p"))
            texts = ["".join((t.text or "") for t in p.findall(".//" + qn("a:t"))) for p in paras]
            print(f"  [{ri},{ci}] n={len(paras)} {texts!r}")
