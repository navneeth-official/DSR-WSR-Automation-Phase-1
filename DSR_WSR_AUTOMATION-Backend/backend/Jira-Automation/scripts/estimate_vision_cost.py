"""Estimate Azure GPT-4o vision cost for one full WSR format evaluation."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def image_tokens(width: int, height: int) -> int:
    """OpenAI gpt-4o vision tokens for detail=high."""
    w, h = float(width), float(height)
    if w > 2048 or h > 2048:
        scale = 2048 / max(w, h)
        w, h = w * scale, h * scale
    scale = 768 / min(w, h)
    w, h = w * scale, h * scale
    tiles = math.ceil(w / 512) * math.ceil(h / 512)
    return int(tiles * 170 + 85)


def parse_run_responses(log_text: str, folder: str) -> list[str]:
    lines = log_text.splitlines()
    responses: list[str] = []
    in_run = False
    for i, line in enumerate(lines):
        if folder in line and "VISION REQUEST" in line:
            in_run = True
        if not in_run:
            continue
        if "VISION RESPONSE" not in line or "attempt=1" not in line:
            continue
        content = line.split("content=", 1)[1]
        j = i + 1
        while j < len(lines) and not re.match(r"^2026-\d{2}-\d{2}T", lines[j]):
            content += "\n" + lines[j]
            j += 1
        responses.append(content)
        if len(responses) == 16:
            break
    return responses


def main() -> None:
    from app.constants.vision_qualitative_reviewer_prompt import (
        QUALITATIVE_VISION_REVIEWER_PROMPT,
    )
    from app.services.ppt_format_extractor import extract_deck
    from app.vision.slide_context import build_vision_context_by_slide

    ppt = ROOT / "output" / "HEB_Delivery_Status.pptx"
    deck = extract_deck(ppt)
    contexts = build_vision_context_by_slide(deck)
    delivery = [s for s in deck["slides"] if 3 <= int(s["slide_index"]) <= 18]

    img_w, img_h = 1920, 1080
    img_tok = image_tokens(img_w, img_h)

    user_jsons: list[str] = []
    for slide in delivery:
        idx = int(slide["slide_index"])
        ctx = dict(contexts[idx])
        ctx.setdefault("title", slide.get("title", ""))
        ctx["review_mode"] = "qualitative"
        payload = {
            "instruction": (
                "Inspect the rendered slide image and return JSON for this slide only."
            ),
            "image_path": f"slide_{idx:02d}.png",
            "slide_number": idx,
        }
        payload.update(ctx)
        user_jsons.append(json.dumps(payload, ensure_ascii=False))

    import tiktoken

    enc = tiktoken.encoding_for_model("gpt-4o")
    sys_tok = len(enc.encode(QUALITATIVE_VISION_REVIEWER_PROMPT))
    user_toks = [len(enc.encode(u)) for u in user_jsons]

    log_path = ROOT / "vision_api_20260721.log"
    log_text = log_path.read_text(encoding="utf-8")
    folder = "ppt_format_eval_vlnzpo12"
    responses = parse_run_responses(log_text, folder)
    out_toks = [len(enc.encode(r)) for r in responses]

    # System prompt is sent on every request (not cached in our code path).
    total_in = 16 * sys_tok + sum(user_toks) + 16 * img_tok
    total_out = sum(out_toks)

    pricing = {
        "Global Standard": (2.50, 10.00),
        "US/EU Data Zone": (2.75, 11.00),
    }

    print("=== WSR AI Visual Evaluation Cost Estimate ===")
    print(f"Deck: {ppt.name}")
    print(f"Delivery slides: {len(delivery)}")
    print(f"Model: gpt-4o (detail=high)")
    print(f"Image export: {img_w}x{img_h} px -> {img_tok} image tokens/slide")
    print(f"System prompt: {sys_tok:,} tokens (x16 requests)")
    print(f"User text payload: {sum(user_toks):,} tokens total "
          f"(avg {sum(user_toks)/len(user_toks):.0f}/slide)")
    print(f"Image tokens: {16 * img_tok:,} total")
    print(f"TOTAL INPUT:  {total_in:,} tokens")
    print(f"TOTAL OUTPUT: {total_out:,} tokens")
    print(f"Log run parsed: {folder} ({len(responses)} responses)")
    print()
    for label, (inp_rate, out_rate) in pricing.items():
        cost = total_in / 1e6 * inp_rate + total_out / 1e6 * out_rate
        print(f"Cost ({label}): ${cost:.4f} USD")
    print()
    print("Per-slide average (Global): "
          f"${(total_in / 1e6 * 2.5 + total_out / 1e6 * 10) / 16:.4f}")


if __name__ == "__main__":
    main()
