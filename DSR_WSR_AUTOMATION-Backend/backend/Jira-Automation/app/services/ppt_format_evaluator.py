"""AI-powered PPT format evaluation against G10X rulebook using configured LLM.

.. deprecated::
    v2.0 hybrid architecture uses deterministic code for all measurable layout
    rules and the visual quality reviewer for subjective assessment.
    This module is retained only for legacy ``mode='ai'`` compatibility.
"""

from __future__ import annotations

import warnings

import json
from pathlib import Path
from typing import Any

from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_violations import compute_service_chains
from app.config import llm_configured
from app.services.llm_client import complete_text

RULEBOOK_PATH = Path(__file__).resolve().parents[1] / "constants" / "ppt_format_rulebook.json"

SYSTEM_PROMPT = """You are a G10X H-E-B WSR delivery-status PowerPoint format auditor.

You receive:
1. The official format rulebook (JSON), including layout_principles.
2. Extracted structural metrics from each slide in the deck under review.
3. service_chains — per-service main + (Contd...) grouping with cross-slide signals.

CONTENT-AGNOSTIC RULE (mandatory):
- NEVER pass or fail a slide by comparing inch heights to a named reference slide (Cost, Supplier, Wentworth, etc.).
- Judge layout using content-relative metrics from layout_principles.metrics_the_ai_must_use and service_chains.

Your job:
- Evaluate EVERY slide titled "Delivery status – …" (main, contd, template placeholders).
- Score EACH slide 0-100 across: typography, bullet_hierarchy, spacing, layout_geometry, content_structure, space_utilization.
- deck_score = average of all delivery-status slide scores; deck_pass when >= threshold.

Layout principle audit checklist (use extracted metrics — human reviewer style):

1. HL internal slack (inside the HL gray box, below last bullet):
   - Metric: hl_waste_below_text_in compared to calibrated bands (dense-fill vs sparse HL+KA).
   - Judge from measured utilization, KA presence, and waste — never from is_contd or main vs contd labels.
   - Flag HL-SIZE-01 / CONT-SPARSE-01 only when waste exceeds the layout-appropriate calibrated band.

2. HL–KA tab spacing (the double-arrow gap — table bottom to KA header):
   - Metric: hl_ka_gap_in ONLY (NOT text_ka_clearance_in, NOT utilization_ratio).
   - Template target: ~0.31 in (~2 body lines). Max allowed: 0.36 in.
   - Flag KA-PLC-02 (major) when hl_ka_gap_in > 0.36 in.
   - When hl_ka_gap_in <= 0.36 in, spacing is CORRECT — do not penalize even if text_ka_clearance_in is larger due to internal HL slack.

3. Overlap (geometry only): KA-OVERLAP-01 if text_ka_clearance_in < 0.15; HL-OVERFLOW-01 if hl_text_overflow_in > 0; GEO-02 if RENDERED text enters footer.

4. Sprint/section spacing: do NOT count blank lines (HL-SPC-03 relaxed). Flag HL-SPC-01 only when category merges with first story.

5. Continuation (context only):
   - service_chains group related slides but must NOT change waste thresholds by slide type.
   - NEVER flag "missing HL tab" on layout_type ka_only_contd (KA-PLC-03).
   - KA-PLC-04: per-slide — HL present, no KA on slide, measured room for KA below HL.

6. Bullets: HL-P-04 critical — category headers Wingdings Ø level 7 only.

7. HL typography (font, size, line spacing inside the HL tab):
   - HL-HDR-02: Highlights header Manrope Bold 14pt
   - HL-P-01..05: body roles use Manrope / Manrope Light 12pt per rulebook roles
   - HL-SPC-02: line spacing 16pt fixed (template spcPts 1600) within story lists
   - HL-SPC-04: story bullets spcBef=0
   - Use highlights.header_metrics, highlights.paragraphs[].runs, line_spacing_pt, spc_bef_pt from extraction.

Penalize: overlaps/clipping, wrong bullets, hl_ka_gap_in > 0.36 in, internal HL waste above calibrated band, HL typography violations (HL-HDR-02, HL-P-01..05, HL-SPC-02, HL-SPC-04).
Do NOT penalize: low utilization when waste is within the layout-appropriate band; hl_ka_gap_in within 0.31–0.36 in band.

Return ONLY valid JSON matching output_schema in rulebook evaluation_instructions. No markdown fences."""


def load_rulebook(path: Path | None = None) -> dict[str, Any]:
    p = path or RULEBOOK_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _build_user_prompt(rulebook: dict, deck_data: dict) -> str:
    # Trim paragraph text in deck data to keep token count reasonable
    compact = json.loads(json.dumps(deck_data))
    for slide in compact.get("slides", []):
        hl = slide.get("highlights")
        if hl and "paragraphs" in hl:
            for p in hl["paragraphs"]:
                if "text" in p and len(p["text"]) > 120:
                    p["text"] = p["text"][:120] + "…"
    return json.dumps(
        {
            "rulebook": rulebook,
            "layout_principles": rulebook.get("layout_principles", {}),
            "service_chains": compute_service_chains(compact.get("slides", [])),
            "deck_under_review": compact,
            "task": (
                "Evaluate format compliance using layout_principles, service_chains, and "
                "content-relative metrics. Use measured layout only — never change thresholds "
                "by is_contd. Never penalize ka_only_contd for missing HL. "
                "Return JSON per output_schema."
            ),
        },
        ensure_ascii=False,
    )


def evaluate_deck_format(
    ppt_path: str | Path,
    rulebook_path: Path | None = None,
) -> dict[str, Any]:
    """
    Extract deck metrics and call the configured LLM for format scoring.
    Returns evaluation JSON with deck_score, deck_pass, per-slide scores.

    .. deprecated:: Use ``evaluate_ppt_format(mode='full')`` for hybrid evaluation.
    """
    warnings.warn(
        "evaluate_deck_format is deprecated; use evaluate_ppt_format(mode='full') "
        "for hybrid deterministic + visual evaluation.",
        DeprecationWarning,
        stacklevel=2,
    )
    rulebook = load_rulebook(rulebook_path)
    deck_data = extract_deck(ppt_path)

    if not deck_data["slides"]:
        return {
            "deck_score": 0,
            "deck_pass": False,
            "slides": [],
            "summary": "No delivery-status slides found in deck.",
            "critical_issues": ["No slides matching 'Delivery status' title pattern."],
        }

    if not llm_configured():
        raise RuntimeError(
            "LLM not configured. Set GEMINI_API_KEY, or AZURE_OPENAI_ENDPOINT "
            "and AZURE_OPENAI_API_KEY, or OPENAI_API_KEY in .env"
        )

    user_prompt = _build_user_prompt(rulebook, deck_data)

    raw = complete_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.1,
        json_mode=True,
    )
    result = json.loads(raw or "{}")

    # Attach extraction snapshot for traceability
    result["source_file"] = deck_data["file"]
    result["extracted_slide_count"] = deck_data["slide_count"]
    result["rulebook_version"] = rulebook.get("meta", {}).get("version", "unknown")

    return result


def format_evaluation_report(result: dict[str, Any]) -> str:
    """Human-readable evaluation summary."""
    lines = [
        f"Deck: {result.get('source_file', '?')}",
        f"Rulebook: v{result.get('rulebook_version', '?')}",
        f"Score: {result.get('deck_score', 0)}/100 — {'PASS' if result.get('deck_pass') else 'FAIL'}",
        "",
        result.get("summary", ""),
        "",
    ]
    if result.get("critical_issues"):
        lines.append("Critical issues:")
        for issue in result["critical_issues"]:
            lines.append(f"  - {issue}")
        lines.append("")

    for slide in result.get("slides", []):
        lines.append(f"Slide {slide.get('slide_index')}: {slide.get('title', '')[:50]}")
        lines.append(f"  Score: {slide.get('score', 0)}/100 — {'PASS' if slide.get('pass') else 'FAIL'}")
        cats = slide.get("category_scores", {})
        if cats:
            lines.append(
                "  Categories: "
                + ", ".join(f"{k}={v}" for k, v in cats.items())
            )
        for v in slide.get("violations", [])[:5]:
            lines.append(f"  [{v.get('severity', '?').upper()}] {v.get('rule_id')}: {v.get('message')}")
        lines.append("")

    return "\n".join(lines)
