"""Debug typography on Location and Pricing slides."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paths import GENERIC_WSR_TEMPLATE
from app.services.wsr_template import resolve_wsr_template
from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_reference import load_evaluation_reference
from app.services.ppt_hl_typography import detect_hl_typography_violations

ref = load_evaluation_reference(resolve_wsr_template(), use_rendered_bounds=False)
deck = extract_deck(
    "output/HEB_Delivery_Status.pptx",
    reference_template=GENERIC_WSR_TEMPLATE,
    category_bullet_spec=ref.typography.category_bullet,
)

lines: list[str] = []
for target in ("Location Core", "Pricing Core"):
    for slide in deck["slides"]:
        title = slide.get("title", "")
        if target not in title:
            continue
        idx = slide["slide_index"]
        hl = slide["highlights"]
        vios = detect_hl_typography_violations(
            hl, slide_index=idx, title=title, typography=ref.typography
        )
        lines.append(f"\n=== SLIDE {idx} {title} ===")
        lines.append(f"violations: {len(vios)}")
        for v in vios:
            lines.append(f"  {v['rule_id']}: {v.get('message')}")
            for d in v.get("details") or []:
                lines.append(
                    f"    issue={d.get('issue')} role={d.get('role')} "
                    f"font={d.get('font')} text={d.get('text') or d.get('paragraph_text')}"
                )
        for i, para in enumerate(hl.get("paragraphs") or []):
            if not para.get("text") or para.get("role") == "blank":
                continue
            text = para.get("text", "")
            role = para.get("role")
            if (
                "warehouse" in text.lower()
                or "Stories" in text
                or role in ("sprint_line", "category_completed", "category_inprogress")
            ):
                runs = para.get("runs") or []
                ri = [
                    (r.get("font"), r.get("bold"), (r.get("text") or "")[:40])
                    for r in runs
                ]
                lines.append(
                    f"  para[{i}] role={role} level={para.get('level')} "
                    f"spc_bef={para.get('spc_bef_pt')} line_sp={para.get('line_spacing_pt')}"
                )
                lines.append(f"    text={text[:100]}")
                lines.append(f"    runs={ri}")

story_spec = ref.typography.role_spec("story_item")
sprint_spec = ref.typography.role_spec("sprint_line")
cat_spec = ref.typography.role_spec("category_completed")
lines.append("\n=== TEMPLATE SPECS ===")
for name, spec in [
    ("sprint_line", sprint_spec),
    ("category_completed", cat_spec),
    ("story_item", story_spec),
]:
    if spec:
        lines.append(
            f"{name}: fonts={sorted(spec.allowed_fonts)} size={spec.size_pt} "
            f"bold={spec.bold} max_spc_bef={spec.max_spc_bef_pt}"
        )

out = ROOT / "output" / "_debug_typography_issues.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out}")
