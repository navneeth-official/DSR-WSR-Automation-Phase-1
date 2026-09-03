"""Prototype HL/KA geometry extracted from the evaluation template."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _spread_tolerance(values: list[float], *, floor: float = 0.02) -> float:
    if len(values) < 2:
        return floor
    spread = max(values) - min(values)
    return round(max(floor, spread / 2 + 0.01), 4)


@dataclass(frozen=True)
class BoxGeometry:
    top: float
    left: float
    width: float
    height: float
    bottom: float


@dataclass(frozen=True)
class TemplateLayoutSpec:
    """Median HL/KA placement from template delivery slides."""

    template_file: str
    prototype_slide_count: int
    hl: BoxGeometry
    ka: BoxGeometry | None
    hl_ka_gap_in: float | None
    title_top_in: float | None
    position_tolerance_in: float
    size_tolerance_in: float


def _box_from_position(position: dict[str, Any]) -> BoxGeometry | None:
    top = position.get("top")
    left = position.get("left")
    width = position.get("width")
    height = position.get("height")
    bottom = position.get("bottom")
    if top is None or width is None or height is None:
        return None
    if left is None:
        left = 0.0
    if bottom is None:
        bottom = float(top) + float(height)
    return BoxGeometry(
        top=round(float(top), 4),
        left=round(float(left), 4),
        width=round(float(width), 4),
        height=round(float(height), 4),
        bottom=round(float(bottom), 4),
    )


def extract_template_layout_spec(deck_data: dict[str, Any]) -> TemplateLayoutSpec | None:
    """
    Build expected HL/KA geometry from measured template delivery slides.

    Uses non-continuation slides with Highlights when available; falls back to
    any slide that exposes HL ``position_in``.
    """
    slides = deck_data.get("slides", [])
    prototypes = [
        s
        for s in slides
        if s.get("highlights") and not s.get("is_contd")
    ] or [s for s in slides if s.get("highlights")]
    if not prototypes:
        return None

    hl_tops: list[float] = []
    hl_lefts: list[float] = []
    hl_widths: list[float] = []
    hl_heights: list[float] = []
    ka_tops: list[float] = []
    ka_lefts: list[float] = []
    ka_widths: list[float] = []
    ka_heights: list[float] = []
    gaps: list[float] = []
    title_tops: list[float] = []

    for slide in prototypes:
        hl_pos = (slide.get("highlights") or {}).get("position_in") or {}
        if hl_pos.get("top") is not None:
            hl_tops.append(float(hl_pos["top"]))
        if hl_pos.get("left") is not None:
            hl_lefts.append(float(hl_pos["left"]))
        if hl_pos.get("width") is not None:
            hl_widths.append(float(hl_pos["width"]))
        if hl_pos.get("height") is not None:
            hl_heights.append(float(hl_pos["height"]))

        ka = slide.get("key_activities")
        if ka:
            ka_pos = ka.get("position_in") or {}
            if ka_pos.get("top") is not None:
                ka_tops.append(float(ka_pos["top"]))
            if ka_pos.get("left") is not None:
                ka_lefts.append(float(ka_pos["left"]))
            if ka_pos.get("width") is not None:
                ka_widths.append(float(ka_pos["width"]))
            if ka_pos.get("height") is not None:
                ka_heights.append(float(ka_pos["height"]))
            gap = slide.get("hl_ka_gap_in")
            if gap is not None:
                gaps.append(float(gap))

        title_pos = slide.get("title_position_in") or {}
        if title_pos.get("top") is not None:
            title_tops.append(float(title_pos["top"]))

    if not hl_tops or not hl_widths or not hl_heights:
        return None

    hl = BoxGeometry(
        top=round(_median(hl_tops), 4),
        left=round(_median(hl_lefts) if hl_lefts else 0.0, 4),
        width=round(_median(hl_widths), 4),
        height=round(_median(hl_heights), 4),
        bottom=round(_median(hl_tops) + _median(hl_heights), 4),
    )
    ka: BoxGeometry | None = None
    if ka_tops and ka_heights:
        ka = BoxGeometry(
            top=round(_median(ka_tops), 4),
            left=round(_median(ka_lefts) if ka_lefts else 0.0, 4),
            width=round(_median(ka_widths), 4) if ka_widths else hl.width,
            height=round(_median(ka_heights), 4),
            bottom=round(_median(ka_tops) + _median(ka_heights), 4),
        )

    position_tol = max(
        _spread_tolerance(hl_tops),
        _spread_tolerance(hl_lefts) if hl_lefts else 0.02,
    )
    size_tol = max(
        _spread_tolerance(hl_widths),
        _spread_tolerance(hl_heights),
    )

    return TemplateLayoutSpec(
        template_file=str(deck_data.get("file", "")),
        prototype_slide_count=len(prototypes),
        hl=hl,
        ka=ka,
        hl_ka_gap_in=round(_median(gaps), 4) if gaps else None,
        title_top_in=round(_median(title_tops), 4) if title_tops else None,
        position_tolerance_in=position_tol,
        size_tolerance_in=size_tol,
    )
