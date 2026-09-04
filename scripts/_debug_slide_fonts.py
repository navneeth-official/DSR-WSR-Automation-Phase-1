"""Debug typography on Supplier Core slide."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.wsr_template import resolve_wsr_template
from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_reference import load_evaluation_reference
from app.services.ppt_hl_typography import detect_hl_typography_violations

template = resolve_wsr_template()
ref = load_evaluation_reference(template, use_rendered_bounds=False)
deck = extract_deck(
    "output/HEB_Delivery_Status.pptx",
    reference_template=template,
    category_bullet_spec=ref.typography.category_bullet,
)

lines: list[str] = []
for slide in deck["slides"]:
    title = slide.get("title", "")
    if "Supplier Core" not in title or slide.get("is_contd"):
        continue
    lines.append(f"SLIDE {slide['slide_index']} {title}")
    hl = slide["highlights"]
    for i, para in enumerate(hl.get("paragraphs") or []):
        if not para.get("text") or para.get("role") == "blank":
            continue
        runs = para.get("runs") or []
        run_info = [
            (r.get("font"), r.get("size_pt"), r.get("bold"), (r.get("text") or "")[:30])
            for r in runs
        ]
        lines.append(f"  [{i}] role={para.get('role')} level={para.get('level')}")
        lines.append(f"      text={repr(para.get('text', '')[:80])}")
        lines.append(f"      runs={run_info}")
    violations = detect_hl_typography_violations(hl, typography=ref.typography)
    lines.append(f"violations {len(violations)} {[v['rule_id'] for v in violations]}")
    for v in violations:
        lines.append(f"  {v['rule_id']} {v.get('message')}")
        for d in v.get("details") or []:
            lines.append(f"    {d}")

out = ROOT / "output" / "_debug_slide4_fonts.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out}")
