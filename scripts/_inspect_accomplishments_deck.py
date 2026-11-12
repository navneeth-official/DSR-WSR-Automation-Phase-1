"""Inspect Accomplishments placeholders and filled bullets in MSR decks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pptx import Presentation

from monthly_report.accomplishments_slide import (
    _statement_paragraphs,
    _statement_text_frame,
    is_accomplishments_slide,
)


def _table_cell_texts(slide) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for shape in slide.shapes:
        if not getattr(shape, "has_table", False) or not shape.has_table:
            continue
        for r_index, row in enumerate(shape.table.rows):
            for c_index, cell in enumerate(row.cells):
                text = (cell.text or "").strip()
                if text:
                    rows.append((f"{shape.name or 'table'}[{r_index},{c_index}]", text))
    return rows


def inspect_template(path: Path) -> None:
    if not path.is_file():
        return
    prs = Presentation(str(path))
    for index, slide in enumerate(prs.slides, 1):
        if not is_accomplishments_slide(slide):
            continue
        frame = _statement_text_frame(slide)
        placeholders = _statement_paragraphs(frame)
        print(f"TEMPLATE {path.name} slide {index}: placeholders={len(placeholders)}")
        print(" ", [p.text for p in placeholders[:10]])


def inspect_deck(path: Path) -> None:
    prs = Presentation(str(path))
    print(f"\n=== DECK {path.name} ({len(prs.slides)} slides) ===")
    for index, slide in enumerate(prs.slides, 1):
        title = slide.shapes.title.text if slide.shapes.title else ""
        cells = _table_cell_texts(slide)
        has_acc = any("accomplish" in text.lower() for _, text in cells)
        if not has_acc and not is_accomplishments_slide(slide):
            continue

        print(f"\nSLIDE {index}: title={title!r}")
        for where, text in cells:
            lower = text.lower()
            if "accomplish" in lower or "statement" in lower or len(text) > 40:
                preview = text.replace("\r", "").replace("\n", " | ")
                print(f"  {where}: len={len(text)} ellipsis={text.rstrip().endswith('...')}")
                print(f"    {preview[:400]!r}")
                # Per-paragraph lengths for body cells
                for shape in slide.shapes:
                    if not getattr(shape, "has_table", False) or not shape.has_table:
                        continue
                    for row in shape.table.rows:
                        for cell in row.cells:
                            if (cell.text or "").strip() != text:
                                continue
                            paras = [
                                (p.text or "").strip()
                                for p in cell.text_frame.paragraphs
                                if (p.text or "").strip()
                            ]
                            if len(paras) > 1 or (paras and len(paras[0]) > 40):
                                print(f"    paragraphs={len(paras)}")
                                for paragraph in paras:
                                    print(
                                        f"      len={len(paragraph)} "
                                        f"ellipsis={paragraph.endswith('...')} "
                                        f"{paragraph!r}"
                                    )


def main() -> None:
    for template in [
        ROOT / "templates" / "monthly" / "G10X_H-E-B_Pricing cadence Meeting Template.pptx",
        ROOT / "templates" / "monthly" / "G10X_H-E-B_MSR_Template_two.pptx",
        ROOT / "G10X_H-E-B_MSR_Template_two.pptx",
    ]:
        inspect_template(template)

    deck = ROOT / "output" / "monthly" / "HEB_MSR_stress_full.pptx"
    if deck.is_file():
        inspect_deck(deck)
    else:
        print("missing", deck)


if __name__ == "__main__":
    main()
