"""Debug HL paragraph spacing on multi-sprint slides."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.wsr_template import resolve_wsr_template
from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_reference import load_evaluation_reference
from app.services.template_block_spec import load_block_spec
from pptx.oxml.ns import qn

ref = load_evaluation_reference(resolve_wsr_template(), use_rendered_bounds=False)
template = resolve_wsr_template()
block = load_block_spec(template, 2)  # first delivery slide in template deck

def spc_bef_pt(p_elem):
    ppr = p_elem.find(qn("a:pPr"))
    if ppr is None:
        return None
    spc = ppr.find(qn("a:spcBef"))
    if spc is None:
        return None
    pt = spc.find(qn("a:spcPts"))
    if pt is None:
        return None
    return int(pt.get("val", 0)) / 100

print("=== TEMPLATE sprint_gap / sprint_line spacing ===")
if block.sprint_gap:
    print("sprint_gap spc_bef:", spc_bef_pt(block.sprint_gap.element))
if block.sprint_line:
    print("sprint_line spc_bef:", spc_bef_pt(block.sprint_line.element))
for para in block.ordered_paragraphs:
    if para.role in ("blank", "sprint_line", "current_week"):
        print(f"  ordered {para.role} spc_bef={spc_bef_pt(para.element)} preview={para.text_preview[:40]!r}")

deck = extract_deck(
    "output/HEB_Delivery_Status.pptx",
    reference_template=template,
    category_bullet_spec=ref.typography.category_bullet,
    label_spec=ref.label_spec,
)
for slide in deck["slides"]:
    title = slide.get("title", "")
    if "Pricing Core" not in title or slide.get("is_contd"):
        continue
    print(f"\n=== {title} ===")
    for i, p in enumerate(slide["highlights"]["paragraphs"]):
        text = (p.get("text") or "").strip()
        print(
            f"  [{i}] role={p.get('role')} spc_bef={p.get('spc_bef_pt')} "
            f"line_sp={p.get('line_spacing_pt')} text={text[:55]!r}"
        )
