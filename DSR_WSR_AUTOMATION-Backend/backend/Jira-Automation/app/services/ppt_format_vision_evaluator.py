"""Vision-based layout inspection of delivery-status slides (pixel measurements + issues)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.constants.vision_layout_inspector_prompt import (
    SLIDE_STATUS_NEEDS_ADJUSTMENT,
    VISION_LAYOUT_INSPECTOR_SYSTEM_PROMPT,
)
from app.services.ppt_slide_images import export_deck_pngs, list_delivery_slide_indices
from app.vision import VisionClient, VisionClientConfig

# Backward-compatible alias for imports expecting the old name.
VISION_SYSTEM_PROMPT = VISION_LAYOUT_INSPECTOR_SYSTEM_PROMPT


def _vision_model() -> str:
    """Prefer a vision-capable deployment; gpt-4o-mini vision is weaker."""
    return (
        os.getenv("AZURE_OPENAI_VISION_MODEL")
        or os.getenv("OPENAI_VISION_MODEL")
        or os.getenv("AZURE_OPENAI_MODEL")
        or "gpt-4o"
    )


def _slide_result_dict(
    result,
    *,
    slide_index: int,
    title: str,
) -> dict[str, Any]:
    """Map typed vision result to the legacy per-slide record shape."""
    data = result.to_dict()
    data["slide_index"] = slide_index
    data["title"] = title
    return data


def evaluate_slide_vision(
    client: VisionClient,
    *,
    image_path: Path,
    slide_index: int,
    title: str,
    template_image_path: Path | None = None,
) -> dict[str, Any]:
    """Inspect one rendered slide image and return measurements + issues."""
    result = client.evaluate(
        image_path,
        template_image=template_image_path,
        slide_number=slide_index,
        context={"title": title},
    )
    return _slide_result_dict(result, slide_index=slide_index, title=title)


def evaluate_deck_vision(
    ppt_path: str | Path,
    *,
    images_dir: str | Path | None = None,
    keep_images: bool = False,
    rulebook_path: Path | None = None,
    vision_client: VisionClient | None = None,
) -> dict[str, Any]:
    """
    Export delivery-status slides to PNG and inspect layout with a vision LLM.

    Returns per-slide pixel measurements and deterministic recommended actions.
    Requires Azure OpenAI or OpenAI with a vision-capable model (gpt-4o recommended).

    ``rulebook_path`` is accepted for CLI compatibility; inspection uses the
    vision layout inspector prompt (rendered pixels), not rulebook inch targets.
    """
    del rulebook_path  # unused — vision inspects rendered layout only
    ppt_path = Path(ppt_path)

    client = vision_client or VisionClient(
        config=VisionClientConfig(model=_vision_model()),
    )
    model = client.config.model or _vision_model()

    if images_dir:
        from app.services.ppt_slide_images import export_slides_to_png

        out_dir = Path(images_dir)
        slide_meta = list_delivery_slide_indices(ppt_path)
        exported = export_slides_to_png(
            ppt_path,
            out_dir,
            slide_indices=[s["slide_index"] for s in slide_meta],
        )
    else:
        out_dir, exported = export_deck_pngs(ppt_path)

    if not exported:
        return {
            "deck_pass": False,
            "deck_score": 0,
            "slides": [],
            "summary": "No delivery-status slides found to export.",
            "critical_issues": ["No slides exported."],
            "evaluator": "vision_layout_inspector",
        }

    slide_results: list[dict[str, Any]] = []
    for entry in exported:
        slide_results.append(
            evaluate_slide_vision(
                client,
                image_path=Path(entry["image_path"]),
                slide_index=entry["slide_index"],
                title=entry["title"],
            )
        )

    deck_pass = all(s.get("pass") for s in slide_results)
    deck_score = (
        round(sum(s.get("score", 0) for s in slide_results) / len(slide_results))
        if slide_results
        else 0
    )
    critical_issues = [
        f"Slide {s['slide_index']}: {i['issue_id']} — {i['explanation']}"
        for s in slide_results
        for i in s.get("issues", [])
        if i.get("severity") == "high"
    ]

    result: dict[str, Any] = {
        "deck_pass": deck_pass,
        "deck_score": deck_score,
        "slides": slide_results,
        "summary": (
            f"Vision layout inspection: {len(slide_results)} slide(s), "
            f"{sum(1 for s in slide_results if s.get('status') == SLIDE_STATUS_NEEDS_ADJUSTMENT)} need adjustment."
        ),
        "critical_issues": critical_issues,
        "source_file": ppt_path.name,
        "evaluator": "vision_layout_inspector",
        "vision_model": model,
        "exported_images": exported,
        "images_dir": str(out_dir),
    }

    if not keep_images and images_dir is None:
        for entry in exported:
            try:
                Path(entry["image_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        try:
            out_dir.rmdir()
        except OSError:
            pass

    return result


def format_vision_report(result: dict[str, Any]) -> str:
    lines = [
        f"Vision layout inspection: {result.get('source_file', '')}",
        f"Model: {result.get('vision_model', '')}",
        f"Deck score: {result.get('deck_score')} ({'PASS' if result.get('deck_pass') else 'FAIL'})",
        "",
    ]
    for slide in result.get("slides", []):
        idx = slide.get("slide_index") or slide.get("slide_number")
        status = slide.get("status") or ("ok" if slide.get("pass") else "needs_adjustment")
        lines.append(f"Slide {idx}: {slide.get('title', '')[:50]} — {status}")
        m = slide.get("measurements") or {}
        if m:
            gap = m.get("gap_between_sections")
            waste = m.get("unused_space_inside_highlight")
            parts = []
            if gap is not None:
                parts.append(f"gap={gap}px")
            if waste is not None:
                parts.append(f"hl_waste={waste}px")
            if parts:
                lines.append(f"  Measurements: {', '.join(parts)}")
        for issue in slide.get("issues") or slide.get("violations") or []:
            action = issue.get("recommended_action", "")
            msg = issue.get("explanation") or issue.get("message", "")
            lines.append(
                f"  [{issue.get('severity')}] {issue.get('issue_id') or issue.get('rule_id')}: "
                f"{msg}"
                + (f" → {action}" if action else "")
            )
        if slide.get("visual_notes"):
            lines.append(f"  Note: {slide['visual_notes']}")
    if result.get("summary"):
        lines.extend(["", result["summary"]])
    return "\n".join(lines)
