"""Debug delivery slide title run formatting."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pptx import Presentation
from pptx.oxml.ns import qn

from app.services.ppt_shape_utils import find_title_shape, slide_title_text
from app.services.wsr_template import resolve_wsr_template


def dump_title(path: str, slide_indices: list[int] | None = None) -> None:
    prs = Presentation(path)
    indices = slide_indices or list(range(len(prs.slides)))
    for i in indices:
        if i >= len(prs.slides):
            continue
        slide = prs.slides[i]
        title = slide_title_text(slide)
        if "delivery" not in title.lower():
            continue
        shape = find_title_shape(slide)
        print(f"=== {path} slide {i + 1}: {title!r}")
        for pi, para in enumerate(shape.text_frame.paragraphs):
            print(f"  para {pi}: runs={len(para.runs)} text={para.text!r}")
            for ri, run in enumerate(para.runs):
                r_pr = run._r.find(qn("a:rPr"))
                if r_pr is None:
                    print(f"    r{ri}: NO rPr")
                    continue
                solid = r_pr.find(qn("a:solidFill"))
                color = None
                if solid is not None:
                    srgb = solid.find(qn("a:srgbClr"))
                    if srgb is not None:
                        color = srgb.get("val")
                print(
                    f"    r{ri}: sz={r_pr.get('sz')} b={r_pr.get('b')} "
                    f"color={color} text={run.text!r}"
                )


if __name__ == "__main__":
    deck = ROOT / "output" / "HEB_Delivery_Status.pptx"
    if deck.is_file():
        dump_title(str(deck), [2, 3])
    tpl = resolve_wsr_template()
    prs = Presentation(str(tpl))
    for i in range(len(prs.slides)):
        t = slide_title_text(prs.slides[i])
        if "delivery" in t.lower() or "track" in t.lower() or "{" in t:
            dump_title(str(tpl), [i])
