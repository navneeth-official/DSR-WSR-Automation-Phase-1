"""One-off inspect cadence meeting deck structure."""
from pathlib import Path

from pptx import Presentation

path = Path(r"C:\Users\AmithKrishnan(G1)XIN\Downloads\G10X_H-E-B_Pricing cadence Meeting 11 Aug 2026.pptx")
prs = Presentation(str(path))
print("Slides:", len(prs.slides))
for i, slide in enumerate(prs.slides):
    print(f"\n=== Slide {i + 1} ===")
    for si, sh in enumerate(slide.shapes):
        if sh.has_text_frame:
            t = sh.text_frame.text.strip()
            if t:
                print(f"  text[{si}]: {t[:300]}")
        if sh.has_table:
            t = sh.table
            print(f"  table[{si}]: {len(t.rows)}x{len(t.columns)}")
            for ri in range(len(t.rows)):
                row = [t.cell(ri, c).text.replace("\n", " ") for c in range(len(t.columns))]
                print(f"    r{ri}: {row}")
