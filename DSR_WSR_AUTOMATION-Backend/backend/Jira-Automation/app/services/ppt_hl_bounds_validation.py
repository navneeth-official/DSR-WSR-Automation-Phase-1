"""Automated validation of HL bounds measurements against rendered slide images."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pptx import Presentation

from app.rendering.com_text_bounds import ComHlTextBounds, ComTextBoundsMeasurer
from app.services.ppt_hl_bounds_debug import (
    HlBoundsDebugSnapshot,
    build_debug_snapshot,
    render_hl_bounds_debug_image,
    scan_text_ink_in_content_region,
)
from app.services.ppt_layout_metrics import EMU_PER_INCH
from app.services.ppt_rendered_bounds import (
    _get_highlights_shape_pptx,
    _hl_content_region_emu,
    measure_hl_text,
)
from app.services.ppt_slide_images import export_slides_to_png

ValidationStatus = Literal["PASS", "FAIL"]


@dataclass
class SlideValidationResult:
    slide_index: int
    title: str
    status: ValidationStatus
    reasons: list[str] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)
    measurement_method: str = ""
    hl_top_in: float = 0.0
    hl_bottom_in: float = 0.0
    text_bottom_in: float = 0.0
    hl_waste_below_text_in: float = 0.0
    debug_image_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "title": self.title,
            "status": self.status,
            "reasons": self.reasons,
            "passes": self.passes,
            "measurement_method": self.measurement_method,
            "hl_top_in": self.hl_top_in,
            "hl_bottom_in": self.hl_bottom_in,
            "text_bottom_in": self.text_bottom_in,
            "hl_waste_below_text_in": self.hl_waste_below_text_in,
            "debug_image_path": self.debug_image_path,
        }


def _is_ink_pixel(r: int, g: int, b: int, *, threshold: int = 200) -> bool:
    return r < threshold and g < threshold and b < threshold


def _count_ink_rows_in_band(
    pixels: Any,
    *,
    x0: int,
    x1: int,
    y0: int,
    y1: int,
    min_span_px: int = 24,
    min_pixels_per_row: int = 5,
    threshold: int = 200,
) -> list[int]:
    """Return y indices (absolute) of rows that look like text ink in a band."""
    ink_rows: list[int] = []
    margin_x = max(4, int((x1 - x0) * 0.04))
    scan_x0 = x0 + margin_x
    scan_x1 = x1 - margin_x
    for y in range(y0, y1):
        count = 0
        for x in range(scan_x0, scan_x1):
            r, g, b = pixels[x, y]
            if _is_ink_pixel(r, g, b, threshold=threshold):
                count += 1
                if count >= min_pixels_per_row:
                    ink_rows.append(y)
                    break
    return ink_rows


def _independent_last_ink_y(
    image_path: Path,
    *,
    scan_roi_px: tuple[int, int, int, int],
    threshold: int = 200,
) -> int | None:
    """Bottom-most ink row in the scan ROI (verification pass)."""
    from PIL import Image

    x0, y0, x1, y1 = scan_roi_px
    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        pixels = rgb.load()
        for y in range(y1 - 1, y0, -1):
            for x in range(x0, x1):
                r, g, b = pixels[x, y]
                if _is_ink_pixel(r, g, b, threshold=threshold):
                    return y
    return None


def _visual_hl_bottom_y(
    image_path: Path,
    *,
    hl_table_px: tuple[int, int, int, int],
) -> int | None:
    """Approximate rendered gray-fill bottom inside the HL table column."""
    from PIL import Image

    x0, y0, x1, y1 = hl_table_px
    xm = (x0 + x1) // 2
    last_gray: int | None = None
    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        for y in range(y0, y1):
            r, g, b = rgb.getpixel((xm, y))
            if 200 <= r <= 248 and 200 <= g <= 248 and 200 <= b <= 248:
                last_gray = y
    return last_gray


def validate_snapshot(
    snapshot: HlBoundsDebugSnapshot,
    image_path: Path | str,
    *,
    px_tolerance: int = 3,
    hl_border_exclude_px: int = 8,
) -> SlideValidationResult:
    """
    Validate one slide's measurement against the rendered PNG.

    Checks: ROI coverage, text-bottom accuracy, no ink in waste band,
    HL container alignment, waste arithmetic.
    """
    image_path = Path(image_path)
    result = SlideValidationResult(
        slide_index=snapshot.slide_index,
        title=snapshot.title,
        status="PASS",
        measurement_method=snapshot.measurement_method,
        hl_top_in=snapshot.hl_top_in,
        hl_bottom_in=snapshot.hl_bottom_in,
        text_bottom_in=snapshot.text_bottom_in,
        hl_waste_below_text_in=snapshot.waste_in,
    )

    if snapshot.measurement_method == "estimated":
        result.status = "FAIL"
        result.reasons.append(
            "Measurement fell back to estimated (COM/image unavailable)"
        )

    # --- ROI must cover full COM content row ---
    if snapshot.scan_roi_in and snapshot.geometry:
        com_row = snapshot.geometry.content_row_com
        scan_bottom = snapshot.scan_roi_in[3]
        if abs(scan_bottom - com_row.bottom) > 0.02:
            result.status = "FAIL"
            result.reasons.append(
                f"Scan ROI bottom ({scan_bottom:.4f} in) does not match COM content row "
                f"({com_row.bottom:.4f} in) — possible ROI clipping"
            )
        else:
            result.passes.append("Scan ROI covers full COM content row")

    # --- Independent ink bottom must match reported blue line ---
    if snapshot.scan_roi_px:
        verify_y = _independent_last_ink_y(image_path, scan_roi_px=snapshot.scan_roi_px)
        if verify_y is None:
            result.status = "FAIL"
            result.reasons.append("No ink detected in scan ROI on verification pass")
        elif abs(verify_y - snapshot.text_bottom_px) > px_tolerance:
            result.status = "FAIL"
            slide_h_px = 1080  # approximate for message only
            result.reasons.append(
                f"Blue line stops {abs(verify_y - snapshot.text_bottom_px)} px above "
                f"independent last-ink row (reported={snapshot.text_bottom_px}, "
                f"verified={verify_y})"
            )
        else:
            result.passes.append("Text detection correct (blue line = last ink)")

    # --- Green bbox must reach last ink ---
    ink_x0, ink_y0, ink_x1, ink_y1 = snapshot.ink_bbox_px
    if abs(ink_y1 - snapshot.text_bottom_px) > px_tolerance:
        result.status = "FAIL"
        result.reasons.append(
            f"Green bbox bottom ({ink_y1}px) misses last ink ({snapshot.text_bottom_px}px)"
        )
    else:
        result.passes.append("Green bbox contains all rendered text")

    # --- No text ink in yellow waste band ---
    if snapshot.scan_roi_px:
        from PIL import Image

        x0, _, x1, _ = snapshot.scan_roi_px
        waste_y0 = snapshot.text_bottom_px + 2
        waste_y1 = snapshot.hl_bottom_px - hl_border_exclude_px
        if waste_y1 > waste_y0:
            with Image.open(image_path) as img:
                pixels = img.convert("RGB").load()
                ink_in_waste = _count_ink_rows_in_band(
                    pixels,
                    x0=x0,
                    x1=x1,
                    y0=waste_y0,
                    y1=waste_y1,
                )
            if ink_in_waste:
                result.status = "FAIL"
                result.reasons.append(
                    f"Visible text inside yellow waste band ({len(ink_in_waste)} ink rows "
                    f"between blue line and HL bottom)"
                )
            else:
                result.passes.append("Waste measurement correct (no text in yellow band)")

    # --- Red boundary vs rendered container (best-effort; gray fill unreliable when dense) ---
    visual_bottom = _visual_hl_bottom_y(image_path, hl_table_px=snapshot.hl_table_px)
    hl_x0, hl_y0, hl_x1, hl_y1 = snapshot.hl_table_px
    com_matches_roi = (
        snapshot.scan_roi_in is not None
        and snapshot.geometry is not None
        and abs(snapshot.scan_roi_in[3] - snapshot.geometry.entire_table_com.bottom) < 0.02
    )
    if com_matches_roi:
        result.passes.append("HL boundary correct (COM table = scan ROI bottom)")

    if visual_bottom is not None:
        delta_px = abs(visual_bottom - snapshot.hl_bottom_px)
        # Gray-fill bottom is unreliable when text fills the cell; tolerate more there.
        border_tolerance = 25 if snapshot.waste_in < 0.08 else 12
        if delta_px > border_tolerance:
            result.status = "FAIL"
            result.reasons.append(
                f"Red HL boundary off by {delta_px} px from rendered gray container bottom"
            )
        elif delta_px > 6:
            result.passes.append(
                f"HL boundary plausible (COM within {delta_px}px of gray fill; "
                "dense fill or anti-alias)"
            )
        else:
            result.passes.append("HL boundary correct (red matches rendered container)")

    # --- Waste arithmetic ---
    expected_waste = round(max(snapshot.hl_bottom_in - snapshot.text_bottom_in, 0.0), 4)
    if abs(expected_waste - snapshot.waste_in) > 0.002:
        result.status = "FAIL"
        result.reasons.append(
            f"hl_waste_below_text_in mismatch: reported {snapshot.waste_in}, "
            f"expected {expected_waste}"
        )

    if result.status == "PASS" and not result.passes:
        result.passes.append("All checks passed")

    return result


def _list_hl_slide_indices(ppt_path: Path) -> list[int]:
    prs = Presentation(str(ppt_path))
    indices: list[int] = []
    for i, slide in enumerate(prs.slides, start=1):
        if _get_highlights_shape_pptx(slide) is not None:
            indices.append(i)
    return indices


def validate_deck(
    ppt_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    slide_indices: list[int] | None = None,
) -> list[SlideValidationResult]:
    """
    Validate HL bounds on every Highlights slide in a deck.

    Exports PNGs once, builds debug overlays, and runs automated checks.
    """
    ppt_path = Path(ppt_path).resolve()
    out_dir = Path(output_dir or ppt_path.parent / "debug" / "hl_validation")
    out_dir.mkdir(parents=True, exist_ok=True)

    indices = slide_indices or _list_hl_slide_indices(ppt_path)
    if not indices:
        return []

    png_dir = out_dir / "slides"
    png_dir.mkdir(parents=True, exist_ok=True)
    exported = export_slides_to_png(ppt_path, png_dir, slide_indices=indices)
    image_by_slide = {int(e["slide_index"]): Path(e["image_path"]) for e in exported}

    results: list[SlideValidationResult] = []
    for slide_index in indices:
        image_path = image_by_slide[slide_index]
        snapshot = build_debug_snapshot(ppt_path, slide_index, image_path=image_path)
        debug_path = out_dir / f"slide_{slide_index:02d}_hl_bounds_debug.png"
        render_hl_bounds_debug_image(image_path, snapshot, debug_path)
        validation = validate_snapshot(snapshot, image_path)
        validation.debug_image_path = str(debug_path)
        results.append(validation)

    return results


def format_validation_report(results: list[SlideValidationResult]) -> str:
    """Human-readable deck validation report."""
    lines: list[str] = []
    passed = sum(1 for r in results if r.status == "PASS")
    failed = len(results) - passed
    lines.append(f"HL Bounds Validation Report — {passed} passed, {failed} failed")
    lines.append("=" * 60)
    lines.append("")

    for r in results:
        lines.append(f"Slide {r.slide_index}")
        lines.append(r.status)
        lines.append(f"Title: {r.title}")
        lines.append(f"Method: {r.measurement_method}")
        lines.append(
            f"HL top/bottom: {r.hl_top_in:.4f} / {r.hl_bottom_in:.4f} in | "
            f"Text bottom: {r.text_bottom_in:.4f} in | "
            f"Waste: {r.hl_waste_below_text_in:.4f} in"
        )
        if r.passes:
            lines.append("Reason:")
            for p in r.passes:
                lines.append(f"- {p}")
        if r.reasons:
            lines.append("Issues:")
            for issue in r.reasons:
                lines.append(f"- {issue}")
        if r.debug_image_path:
            lines.append(f"Debug: {r.debug_image_path}")
        lines.append("")

    return "\n".join(lines)
