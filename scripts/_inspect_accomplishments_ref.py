"""One-off: compare accomplishments slide formatting in reference vs built deck."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from pptx import Presentation
from pptx.enum.dml import MSO_COLOR_TYPE

from monthly_report.accomplishments_slide import is_accomplishments_slide


def _run_info(run):
    color = None
    if run.font.color.type == MSO_COLOR_TYPE.RGB:
        color = str(run.font.color.rgb)
    elif run.font.color.type == MSO_COLOR_TYPE.SCHEME:
        color = f"theme:{run.font.color.theme_color}"
    return {
        "text": run.text,
        "size": run.font.size.pt if run.font.size else None,
        "bold": run.font.bold,
        "name": run.font.name,
        "color": color,
    }


def dump_cell(cell, prefix: str) -> None:
    print(f"{prefix} text: {cell.text!r}")
    tf = cell.text_frame
    for pi, para in enumerate(tf.paragraphs):
        runs = [_run_info(r) for r in para.runs if r.text]
        print(f"{prefix} p{pi} level={para.level} runs={runs}")


def dump_slide(slide, index: int) -> None:
    print(f"--- slide {index} ---")
    if slide.shapes.title:
        print("TITLE:", repr(slide.shapes.title.text))
    for j, shape in enumerate(slide.shapes):
        if shape.has_table:
            table = shape.table
            for r in range(len(table.rows)):
                for c in range(len(table.columns)):
                    dump_cell(table.cell(r, c), f"table[{r},{c}]")
        elif shape.has_text_frame and shape.text_frame.text.strip():
            print(f"shape{j}:", repr(shape.text_frame.text[:300]))


def dump_deck(path: Path, label: str) -> None:
    prs = Presentation(str(path))
    print(f"\n=== {label}: {path.name} ({len(prs.slides)} slides) ===")
    found = False
    for i, slide in enumerate(prs.slides):
        if is_accomplishments_slide(slide):
            found = True
            dump_slide(slide, i)
    if not found:
        print("(no accomplishments table slide found)")


def main() -> None:
    ref = Path(
        r"C:\Users\AmithKrishnan(G1)XIN\Downloads\G10X_H-E-B_Supplier_Cadence Meeting 14 Oct 2026.pptx"
    )
    monthly = Path(__file__).resolve().parents[1] / "output" / "monthly"
    outs = sorted(monthly.glob("HEB*.pptx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ref.is_file():
        dump_deck(ref, "REFERENCE")
    else:
        print("Reference missing:", ref)
    if outs:
        dump_deck(outs[0], "BUILT")
    else:
        print("No built monthly deck in output/monthly")


if __name__ == "__main__":
    main()
