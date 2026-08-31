"""
Generate annotated debug image for HL text bounds measurement.

Usage:
    python scripts/debug_hl_bounds_slide.py --slide 12
    python scripts/debug_hl_bounds_slide.py --slide 12 --ppt output/HEB_Delivery_Status.pptx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ppt_hl_bounds_debug import (
    format_geometry_report,
    format_scan_roi_report,
    generate_hl_bounds_debug_image,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export annotated HL bounds debug image for one slide."
    )
    parser.add_argument("--ppt", default="output/HEB_Delivery_Status.pptx")
    parser.add_argument("--slide", type=int, default=12)
    parser.add_argument(
        "--out",
        default="",
        help="Output PNG path (default: output/debug/slide_NN_hl_bounds_debug.png)",
    )
    args = parser.parse_args()

    ppt = Path(args.ppt).resolve()
    if not ppt.is_file():
        raise SystemExit(f"PPT not found: {ppt}")

    out = (
        Path(args.out).resolve()
        if args.out
        else ppt.parent / "debug" / f"slide_{args.slide:02d}_hl_bounds_debug.png"
    )

    result = generate_hl_bounds_debug_image(ppt, args.slide, out)
    print(f"Debug image -> {result['output_path']}")
    print(f"Slide {result['slide_index']}: {result['title']}")
    print(f"method: {result['measurement_method']}")
    print(f"hl_waste_below_text_in: {result['hl_waste_below_text_in']:.4f} in")
    print(f"text_bottom_in (image): {result['text_bottom_in']:.4f} in")
    print(f"hl_bottom_in (COM):     {result['hl_bottom_in']:.4f} in")
    if result.get("com_text_bottom_in") is not None:
        print(f"com_text_bottom_in:     {result['com_text_bottom_in']:.4f} in")
    if result.get("geometry_report"):
        print()
        print(result["geometry_report"])
    if result.get("scan_roi_report"):
        print()
        print(result["scan_roi_report"])


if __name__ == "__main__":
    main()
