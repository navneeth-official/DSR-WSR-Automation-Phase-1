"""Layout thresholds derived from calibrated delivery-status decks (not arbitrary inches)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.paths import REPO_ROOT
from app.services.ppt_layout_metrics import UTILIZATION_THRESHOLD

THRESHOLDS_PATH = (
    REPO_ROOT / "app" / "constants" / "template_layout_thresholds.json"
)
TEMPLATE_PATH = REPO_ROOT / "templates" / "G10X H-E-B WSR Sustainment 05 June 2026 .pptx"
APPROVED_DECK_PATH = REPO_ROOT / "output" / "HEB_Delivery_Status.pptx"

# Legacy JSON keys kept for backward-compatible loading.
_LEGACY_THRESHOLD_ALIASES: dict[str, str] = {
    "hl_waste_dense_main_max_in": "hl_waste_dense_fill_max_in",
    "hl_waste_sparse_contd_max_in": "hl_waste_sparse_ka_max_in",
    "dense_main_min_effective_util": "hl_dense_fill_min_effective_util",
}


@dataclass(frozen=True)
class TemplateLayoutThresholds:
    """
    Human-reviewer-style tolerances calibrated from approved WSR slides.
    Values are empirical bands from the reference deck, not assumed inches.
    """

    min_text_ka_clearance_in: float = 0.15
    hl_text_overflow_tolerance_in: float = 0.05
    footer_content_max_bottom_in: float = 6.29
    hl_waste_extreme_in: float = 2.4
    hl_waste_stretch_max_util: float = 0.20
    ka_waste_extreme_in: float = 1.2
    ka_waste_stretch_max_util: float = 0.20
    hl_ka_clearance_typical_max_in: float = 2.2
    hl_waste_below_text_typical_max_in: float = 0.12
    hl_waste_dense_fill_max_in: float = 0.12
    hl_waste_contd_hl_max_in: float = 0.12
    hl_waste_sparse_ka_max_in: float = 1.05
    hl_ka_border_gap_target_in: float = 0.3111
    hl_ka_border_gap_max_in: float = 0.33
    hl_dense_fill_min_effective_util: float = UTILIZATION_THRESHOLD
    footer_text_min_margin_in: float = 0.15
    template_file: str = ""
    calibrated_slide_count: int = 0
    calibration_notes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemplateLayoutThresholds:
        normalized = dict(data)
        for legacy_key, new_key in _LEGACY_THRESHOLD_ALIASES.items():
            if new_key not in normalized and legacy_key in normalized:
                normalized[new_key] = normalized[legacy_key]
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in normalized.items() if k in known}
        if "calibration_notes" in filtered and isinstance(filtered["calibration_notes"], list):
            filtered["calibration_notes"] = tuple(filtered["calibration_notes"])
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_text_ka_clearance_in": self.min_text_ka_clearance_in,
            "hl_text_overflow_tolerance_in": self.hl_text_overflow_tolerance_in,
            "footer_content_max_bottom_in": self.footer_content_max_bottom_in,
            "hl_waste_extreme_in": self.hl_waste_extreme_in,
            "hl_waste_stretch_max_util": self.hl_waste_stretch_max_util,
            "ka_waste_extreme_in": self.ka_waste_extreme_in,
            "ka_waste_stretch_max_util": self.ka_waste_stretch_max_util,
            "hl_ka_clearance_typical_max_in": self.hl_ka_clearance_typical_max_in,
            "hl_waste_below_text_typical_max_in": self.hl_waste_below_text_typical_max_in,
            "hl_waste_dense_fill_max_in": self.hl_waste_dense_fill_max_in,
            "hl_waste_contd_hl_max_in": self.hl_waste_contd_hl_max_in,
            "hl_waste_sparse_ka_max_in": self.hl_waste_sparse_ka_max_in,
            "hl_ka_border_gap_target_in": self.hl_ka_border_gap_target_in,
            "hl_ka_border_gap_max_in": self.hl_ka_border_gap_max_in,
            "hl_dense_fill_min_effective_util": self.hl_dense_fill_min_effective_util,
            "footer_text_min_margin_in": self.footer_text_min_margin_in,
            "template_file": self.template_file,
            "calibrated_slide_count": self.calibrated_slide_count,
            "calibration_notes": list(self.calibration_notes),
        }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * pct))))
    return ordered[idx]


def _hl_effective_util(slide: dict[str, Any]) -> float | None:
    hl = slide.get("highlights") or {}
    util = hl.get("effective_utilization_ratio", hl.get("utilization_ratio"))
    return float(util) if util is not None else None


def _hl_table_bottom_in(slide: dict[str, Any]) -> float | None:
    measured = slide.get("hl_bottom_measured_in")
    if measured is not None:
        return float(measured)
    hl = slide.get("highlights") or {}
    bottom = hl.get("position_in", {}).get("bottom")
    return float(bottom) if bottom is not None else None


def _is_hl_dense_fill(slide: dict[str, Any], *, dense_util: float) -> bool:
    if not slide.get("highlights"):
        return False
    util = _hl_effective_util(slide)
    return util is not None and util >= dense_util


def _is_sparse_hl_with_ka(slide: dict[str, Any], *, dense_util: float) -> bool:
    if slide.get("key_activities") is None or not slide.get("highlights"):
        return False
    util = _hl_effective_util(slide)
    return util is not None and util < dense_util


def analyze_deck_for_calibration(deck_data: dict[str, Any]) -> dict[str, Any]:
    """Collect per-metric stats used to derive thresholds."""
    slides = [s for s in deck_data.get("slides", []) if s.get("highlights")]
    dense_util = UTILIZATION_THRESHOLD

    dense_fill = [_s for _s in slides if _is_hl_dense_fill(_s, dense_util=dense_util)]
    sparse_hl_ka = [_s for _s in slides if _is_sparse_hl_with_ka(_s, dense_util=dense_util)]

    def collect(key: str, subset: list[dict[str, Any]] | None = None) -> list[float]:
        src = subset if subset is not None else slides
        out: list[float] = []
        for slide in src:
            val = slide.get(key)
            if val is not None:
                out.append(float(val))
        return out

    def hl_wastes(subset: list[dict[str, Any]]) -> list[float]:
        return [
            float(s["hl_waste_below_text_in"])
            for s in subset
            if s.get("hl_waste_below_text_in") is not None
        ]

    text_bottoms = collect("rendered_text_bottom_in") or collect("estimated_text_bottom_in")
    hl_bottoms = [_hl_table_bottom_in(s) for s in slides]
    hl_bottoms = [b for b in hl_bottoms if b is not None]

    gaps = collect("hl_ka_gap_in")
    clearances = collect("text_ka_clearance_in")
    ka_wastes = collect("ka_waste_below_text_in")
    utils = [
        float(s["highlights"]["effective_utilization_ratio"])
        for s in slides
        if s["highlights"].get("effective_utilization_ratio") is not None
    ]

    dense_wastes = hl_wastes(dense_fill)
    sparse_wastes = hl_wastes(sparse_hl_ka)

    return {
        "slide_count": len(slides),
        "dense_fill_count": len(dense_fill),
        "sparse_hl_ka_count": len(sparse_hl_ka),
        "hl_waste_all": hl_wastes(slides),
        "hl_waste_dense_fill": dense_wastes,
        "hl_waste_sparse_hl_ka": sparse_wastes,
        "hl_ka_gap": gaps,
        "text_ka_clearance": clearances,
        "ka_waste": ka_wastes,
        "effective_util": utils,
        "rendered_text_bottom": text_bottoms,
        "hl_table_bottom": hl_bottoms,
    }


def calibrate_from_deck(deck_data: dict[str, Any]) -> TemplateLayoutThresholds:
    """
    Derive evaluation thresholds from an extracted, measured delivery-status deck.

    Segments dense-fill vs sparse HL+KA slides by measured utilization and KA
    presence — not by main vs continuation labels.
    """
    stats = analyze_deck_for_calibration(deck_data)
    notes: list[str] = []

    dense_wastes = stats["hl_waste_dense_fill"]
    sparse_wastes = stats["hl_waste_sparse_hl_ka"]
    gaps = stats["hl_ka_gap"]
    clearances = stats["text_ka_clearance"]
    ka_wastes = stats["ka_waste"]
    text_bottoms = stats["rendered_text_bottom"]

    dense_p95 = _percentile(dense_wastes, 0.95) if dense_wastes else 0.11
    sparse_p95 = _percentile(sparse_wastes, 0.95) if sparse_wastes else 1.0
    gap_p50 = _percentile(gaps, 0.50) if gaps else 0.3111
    gap_max = max(gaps) if gaps else gap_p50
    clr_p95 = _percentile(clearances, 0.95) if clearances else 1.5
    ka_waste_p95 = _percentile(ka_wastes, 0.95) if ka_wastes else 0.0

    hl_waste_dense_fill_max = round(max(dense_p95 + 0.02, 0.10), 4)
    hl_waste_sparse_ka_max = round(max(sparse_p95 + 0.05, 0.5), 4)
    hl_ka_target = round(gap_p50, 4)
    hl_ka_max = round(max(gap_max + 0.02, hl_ka_target + 0.02), 4)

    reference_footer_in = 6.29
    max_text_bottom = max(text_bottoms) if text_bottoms else reference_footer_in
    text_margins = [
        reference_footer_in - t for t in text_bottoms if t <= reference_footer_in + 0.01
    ]
    min_margin = min(text_margins) if text_margins else 0.15
    footer_min_margin = round(max(min(min_margin, 0.20), 0.12), 4)
    footer_max = round(max(max_text_bottom + footer_min_margin, reference_footer_in), 4)

    hl_waste_extreme = round(
        max(sparse_p95 * 1.15, hl_waste_sparse_ka_max + 0.25, 1.2), 4
    )

    notes.append(
        f"Dense-fill HL waste p95={dense_p95:.4f} in → max acceptable {hl_waste_dense_fill_max:.4f} in"
    )
    notes.append(
        f"HL (Contd…) internal waste uses dense-fill band ({hl_waste_dense_fill_max:.4f} in) — "
        "shrink the HL table on continuation slides instead of keeping the main-slide box height"
    )
    notes.append(
        f"Sparse HL+KA waste p95={sparse_p95:.4f} in → max acceptable {hl_waste_sparse_ka_max:.4f} in"
    )
    notes.append(
        f"HL–KA border gap observed {gap_p50:.4f}–{gap_max:.4f} in → target {hl_ka_target:.4f}, max {hl_ka_max:.4f} in"
    )
    notes.append(
        f"Footer: max text bottom {max_text_bottom:.4f} in, min margin {min_margin:.4f} in → limit {footer_max:.4f} in"
    )

    return TemplateLayoutThresholds(
        min_text_ka_clearance_in=0.15,
        hl_text_overflow_tolerance_in=0.05,
        footer_content_max_bottom_in=footer_max,
        hl_waste_extreme_in=hl_waste_extreme,
        hl_waste_stretch_max_util=0.20,
        ka_waste_extreme_in=round(max(ka_waste_p95 + 0.25, 0.5), 4),
        ka_waste_stretch_max_util=0.20,
        hl_ka_clearance_typical_max_in=round(max(clr_p95 * 1.05, 1.0), 4),
        hl_waste_below_text_typical_max_in=hl_waste_dense_fill_max,
        hl_waste_dense_fill_max_in=hl_waste_dense_fill_max,
        hl_waste_contd_hl_max_in=hl_waste_dense_fill_max,
        hl_waste_sparse_ka_max_in=hl_waste_sparse_ka_max,
        hl_ka_border_gap_target_in=hl_ka_target,
        hl_ka_border_gap_max_in=hl_ka_max,
        hl_dense_fill_min_effective_util=UTILIZATION_THRESHOLD,
        footer_text_min_margin_in=footer_min_margin,
        template_file=deck_data.get("file", TEMPLATE_PATH.name),
        calibrated_slide_count=int(stats["slide_count"]),
        calibration_notes=tuple(notes),
    )


def format_calibration_report(
    deck_data: dict[str, Any],
    thresholds: TemplateLayoutThresholds,
) -> str:
    """Human-readable summary of observed ranges and derived thresholds."""
    stats = analyze_deck_for_calibration(deck_data)
    lines = [
        "Template layout calibration report",
        f"Source deck: {thresholds.template_file}",
        f"Highlights slides analyzed: {thresholds.calibrated_slide_count}",
        "",
        "Observed ranges",
        "---------------",
    ]

    def band(name: str, values: list[float]) -> None:
        if not values:
            return
        lines.append(
            f"{name}: min={min(values):.4f} p50={_percentile(values, 0.5):.4f} "
            f"p95={_percentile(values, 0.95):.4f} max={max(values):.4f} (n={len(values)})"
        )

    band("HL internal waste (all)", stats["hl_waste_all"])
    band("HL internal waste (dense fill)", stats["hl_waste_dense_fill"])
    band("HL internal waste (sparse HL+KA)", stats["hl_waste_sparse_hl_ka"])
    band("HL–KA border gap", stats["hl_ka_gap"])
    band("Text–KA clearance", stats["text_ka_clearance"])
    band("KA internal waste", stats["ka_waste"])
    band("Effective HL utilization", stats["effective_util"])
    band("Rendered text bottom", stats["rendered_text_bottom"])

    lines.extend(["", "Derived thresholds", "----------------"])
    for key, val in thresholds.to_dict().items():
        if key in ("template_file", "calibrated_slide_count", "calibration_notes"):
            continue
        lines.append(f"{key}: {val}")

    if thresholds.calibration_notes:
        lines.extend(["", "Notes"])
        lines.extend(f"- {note}" for note in thresholds.calibration_notes)

    return "\n".join(lines)


def load_thresholds(path: Path | None = None) -> TemplateLayoutThresholds:
    p = path or THRESHOLDS_PATH
    if p.is_file():
        with open(p, encoding="utf-8") as f:
            return TemplateLayoutThresholds.from_dict(json.load(f))
    return TemplateLayoutThresholds()


def save_thresholds(thresholds: TemplateLayoutThresholds, path: Path | None = None) -> Path:
    p = path or THRESHOLDS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(thresholds.to_dict(), f, indent=2)
        f.write("\n")
    return p
