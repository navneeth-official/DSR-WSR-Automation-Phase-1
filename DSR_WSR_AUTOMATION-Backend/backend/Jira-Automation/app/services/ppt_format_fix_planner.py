"""GPT-4o mini FixPlan service for post-build PPT layout repair."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.ppt_format_evaluator import load_rulebook
from app.config import llm_configured
from app.services.llm_client import complete_text

ALLOWED_ACTIONS = frozenset({
    "reflow_hl_ka",
    "fix_category_bullets",
    "remove_extra_sprint_blanks",
    "remove_category_story_blanks",
    "shrink_sparse_hl",
    "layout_repair",
    "fix_title_en_dash",
    "rebuild_with_hints",
})

SYSTEM_PROMPT = """You are a G10X H-E-B WSR delivery-status PowerPoint layout repair planner.

Follow layout_principles in the rulebook — content-agnostic rules that scale with content volume.
NEVER plan fixes by matching inch heights to a named reference slide.

You receive:
1. Format rulebook repair_instructions and layout_principles.
2. Extracted deck metrics (compact).
3. Deterministic violations already detected.

Return ONLY valid JSON matching repair_instructions.output_schema:
{ "fixes": [...], "reason": "..." }

Violation → fix mapping:
- TITLE-01 → fix_title_en_dash
- KA-OVERLAP-01 / KA-PLC-01 / KA-PLC-02 / HL-SIZE-01 / KA-SIZE-01 / CONT-SPARSE-01 / GEO-02 → layout_repair
- KA-OVERLAP-01 may also use reflow_hl_ka
- HL-P-04 → fix_category_bullets
- HL-SPC-01 → remove_category_story_blanks
- HL-SPC-03 → remove_extra_sprint_blanks
- HL-UTIL-01 → rebuild_with_hints (pack_all_sections_on_main, suppress_hl_contd)
- KA-PLC-04 → layout_repair (+ rebuild_with_hints if needed)

Prefer layout_repair and in-place fixes before rebuild_with_hints.
service_title = service name without "Delivery status" prefix.
No markdown fences."""


def _compact_deck(deck_data: dict[str, Any]) -> dict[str, Any]:
    compact = json.loads(json.dumps(deck_data))
    for slide in compact.get("slides", []):
        hl = slide.get("highlights")
        if hl and "paragraphs" in hl:
            for p in hl["paragraphs"]:
                if "text" in p and len(p["text"]) > 80:
                    p["text"] = p["text"][:80] + "…"
            hl.pop("paragraphs", None)
    return compact


def _service_title(title: str) -> str:
    base = re.sub(r"^Delivery status\s*[–-]\s*", "", title, flags=re.I)
    return re.sub(r"\s*\(Contd.*\)\s*$", "", base, flags=re.I).strip()


def _validate_fix(fix: dict[str, Any]) -> dict[str, Any] | None:
    action = fix.get("action")
    if action not in ALLOWED_ACTIONS:
        return None
    cleaned: dict[str, Any] = {"action": action, "params": fix.get("params") or {}}
    if fix.get("slide_index") is not None:
        cleaned["slide_index"] = int(fix["slide_index"])
    if fix.get("service_title"):
        cleaned["service_title"] = str(fix["service_title"]).strip()
    return cleaned


def _deterministic_fallback(violations: list[dict[str, Any]]) -> dict[str, Any]:
    """Rule-based FixPlan when LLM is unavailable."""
    fixes: list[dict[str, Any]] = []
    seen_rebuild: set[str] = set()

    for v in violations:
        rule_id = v.get("rule_id", "")
        slide_index = v.get("slide_index")
        service = v.get("service_title") or _service_title(v.get("title", ""))

        if rule_id == "TITLE-01" and slide_index:
            fixes.append({
                "action": "fix_title_en_dash",
                "slide_index": slide_index,
                "service_title": service,
                "params": {},
            })
        elif rule_id in ("KA-OVERLAP-01", "KA-PLC-01", "KA-PLC-02") and slide_index:
            fixes.append({
                "action": "layout_repair",
                "slide_index": slide_index,
                "service_title": service,
                "params": {"layout_mode": "expanded"},
            })
            if rule_id == "KA-OVERLAP-01":
                fixes.append({
                    "action": "reflow_hl_ka",
                    "slide_index": slide_index,
                    "service_title": service,
                    "params": {"expand_for_wrap": True, "layout_mode": "expanded"},
                })
        elif rule_id == "HL-P-04" and slide_index:
            fixes.append({
                "action": "fix_category_bullets",
                "slide_index": slide_index,
                "service_title": service,
                "params": {},
            })
        elif rule_id == "HL-SPC-01" and slide_index:
            fixes.append({
                "action": "remove_category_story_blanks",
                "slide_index": slide_index,
                "service_title": service,
                "params": {},
            })
        elif rule_id == "HL-SPC-03" and slide_index:
            fixes.append({
                "action": "remove_extra_sprint_blanks",
                "slide_index": slide_index,
                "service_title": service,
                "params": {},
            })
        elif rule_id == "CONT-SPARSE-01" and slide_index:
            fixes.append({
                "action": "layout_repair",
                "slide_index": slide_index,
                "service_title": service,
                "params": {"layout_mode": "normal"},
            })
        elif rule_id == "HL-SIZE-01" and slide_index:
            fixes.append({
                "action": "layout_repair",
                "slide_index": slide_index,
                "service_title": service,
                "params": {"layout_mode": "normal"},
            })
        elif rule_id == "KA-SIZE-01" and slide_index:
            fixes.append({
                "action": "layout_repair",
                "slide_index": slide_index,
                "service_title": service,
                "params": {"layout_mode": "normal", "tighten_ka": True},
            })
        elif rule_id == "GEO-02" and slide_index:
            fixes.append({
                "action": "layout_repair",
                "slide_index": slide_index,
                "service_title": service,
                "params": {"layout_mode": "expanded"},
            })
            if service and service not in seen_rebuild:
                seen_rebuild.add(service)
                fixes.append({
                    "action": "rebuild_with_hints",
                    "service_title": service,
                    "params": {"pack_all_sections_on_main": True},
                })
        elif rule_id == "KA-PLC-04" and slide_index:
            fixes.append({
                "action": "layout_repair",
                "slide_index": slide_index,
                "service_title": service,
                "params": {"layout_mode": "normal"},
            })
            fixes.append({
                "action": "reflow_hl_ka",
                "slide_index": slide_index,
                "service_title": service,
                "params": {"expand_for_wrap": True, "layout_mode": "expanded"},
            })
            if service and service not in seen_rebuild:
                seen_rebuild.add(service)
                fixes.append({
                    "action": "rebuild_with_hints",
                    "service_title": service,
                    "params": {"keep_ka_on_main_when_fits": True},
                })
        elif rule_id == "HL-UTIL-01" and service and service not in seen_rebuild:
            seen_rebuild.add(service)
            fixes.append({
                "action": "rebuild_with_hints",
                "service_title": service,
                "params": {
                    "pack_all_sections_on_main": True,
                    "suppress_hl_contd": True,
                },
                })

    return {
        "fixes": fixes,
        "reason": "Deterministic fallback from violation rules",
        "planner": "deterministic",
    }


def plan_fixes(
    deck_data: dict[str, Any],
    violations_report: dict[str, Any],
    rulebook_path: Path | None = None,
) -> dict[str, Any]:
    """
    Return FixPlan JSON for detected violations.
    Uses GPT-4o mini when configured; falls back to deterministic mapping.
    """
    violations = violations_report.get("violations", [])
    if not violations:
        return {"fixes": [], "reason": "No violations to fix", "planner": "none"}

    rulebook = load_rulebook(rulebook_path)
    repair = rulebook.get("repair_instructions", {})

    if not llm_configured():
        return _deterministic_fallback(violations)

    user_payload = {
        "repair_instructions": repair,
        "layout_principles": rulebook.get("layout_principles", {}),
        "deck_metrics": _compact_deck(deck_data),
        "violations": violations,
        "task": "Return FixPlan JSON per output_schema. Only whitelisted actions.",
    }

    raw = complete_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=json.dumps(user_payload, ensure_ascii=False),
        temperature=0.1,
        json_mode=True,
    )
    plan = json.loads(raw or "{}")
    validated = [
        f for f in (_validate_fix(x) for x in plan.get("fixes", [])) if f is not None
    ]
    det = _deterministic_fallback(violations)
    seen = {
        (f.get("slide_index"), f.get("action"), f.get("service_title"))
        for f in validated
    }
    for fix in det.get("fixes", []):
        key = (fix.get("slide_index"), fix.get("action"), fix.get("service_title"))
        if key not in seen:
            validated.append(fix)
            seen.add(key)
    if not validated:
        return det

    return {
        "fixes": validated,
        "reason": plan.get("reason", ""),
        "planner": "gpt+deterministic",
    }
