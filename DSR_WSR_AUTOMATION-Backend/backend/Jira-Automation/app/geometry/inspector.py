"""Inspect delivery-status decks using deterministic PowerPoint geometry."""

from __future__ import annotations

from pathlib import Path

from app.geometry.metrics import enrich_slide_metrics
from app.geometry.types import GeometryReport, GeometryViolation, SlideGeometryReport
from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_violations import detect_deck_violations


class GeometryInspector:
    """
    Authoritative numeric layout inspection from PPTX structure and EMU metrics.

    Uses ``ppt_format_extractor`` + ``ppt_format_violations`` — the same
    deterministic path as the legacy rulebook repair loop.
    """

    def inspect(self, ppt_path: Path | str) -> GeometryReport:
        path = Path(ppt_path).resolve()
        deck = extract_deck(path)
        deck_result = detect_deck_violations(deck, scope_all_slides=True)
        violations_by_slide: dict[int, list[dict]] = {}
        for violation in deck_result.get("violations") or []:
            idx = violation.get("slide_index")
            if idx is not None:
                violations_by_slide.setdefault(int(idx), []).append(violation)

        slides: list[SlideGeometryReport] = []
        total_violations = deck_result.get("violation_count", 0)
        critical_count = deck_result.get("critical_count", 0)

        for slide_data in deck.get("slides") or []:
            idx = int(slide_data.get("slide_index") or 0)
            raw_violations = violations_by_slide.get(idx, [])
            violations = [GeometryViolation.from_dict(v) for v in raw_violations]

            metrics = {
                k: slide_data.get(k)
                for k in (
                    "text_ka_clearance_in",
                    "hl_ka_gap_in",
                    "hl_waste_below_text_in",
                    "ka_waste_below_text_in",
                    "estimated_text_bottom_in",
                    "hl_text_bottom_for_fit_in",
                )
                if slide_data.get(k) is not None
            }
            hl = slide_data.get("highlights") or {}
            ka = slide_data.get("key_activities") or {}
            if hl.get("position_in"):
                metrics["hl_position_in"] = hl["position_in"]
            if ka.get("position_in"):
                metrics["ka_position_in"] = ka["position_in"]

            metrics = enrich_slide_metrics(metrics)

            slides.append(
                SlideGeometryReport(
                    slide_index=idx,
                    title=str(slide_data.get("title") or ""),
                    layout_type=str(slide_data.get("layout_type") or "unknown"),
                    metrics=metrics,
                    violations=violations,
                )
            )

        return GeometryReport(
            ppt_path=str(path),
            slides=slides,
            violation_count=total_violations,
            critical_count=critical_count,
        )
