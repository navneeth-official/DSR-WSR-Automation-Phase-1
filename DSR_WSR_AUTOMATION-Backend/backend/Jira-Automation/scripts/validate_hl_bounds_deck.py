"""
Validate HL bounds measurements across an entire WSR deck.

Usage:
    python scripts/validate_hl_bounds_deck.py
    python scripts/validate_hl_bounds_deck.py --ppt output/HEB_Delivery_Status.pptx
    python scripts/validate_hl_bounds_deck.py --slide 3 4 11
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ppt_hl_bounds_validation import (
    format_validation_report,
    validate_deck,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate HL text bounds measurements for all Highlights slides."
    )
    parser.add_argument(
        "--ppt",
        default="output/HEB_Delivery_Status.pptx",
        help="Path to WSR .pptx deck",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output directory (default: output/debug/hl_validation)",
    )
    parser.add_argument(
        "--slide",
        type=int,
        nargs="*",
        help="Optional slide indices (default: all HL slides)",
    )
    args = parser.parse_args()

    ppt = Path(args.ppt).resolve()
    if not ppt.is_file():
        raise SystemExit(f"PPT not found: {ppt}")

    out_dir = Path(args.out).resolve() if args.out else ppt.parent / "debug" / "hl_validation"

    results = validate_deck(
        ppt,
        output_dir=out_dir,
        slide_indices=args.slide or None,
    )

    report = format_validation_report(results)
    sys.stdout.buffer.write(report.encode("utf-8", errors="replace"))
    sys.stdout.buffer.write(b"\n")

    report_path = out_dir / "validation_report.txt"
    report_path.write_text(report, encoding="utf-8")

    json_path = out_dir / "validation_report.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2),
        encoding="utf-8",
    )

    print(f"\nReport -> {report_path}")
    print(f"JSON   -> {json_path}")

    failed = [r for r in results if r.status == "FAIL"]
    if failed:
        raise SystemExit(f"{len(failed)} slide(s) failed validation")


if __name__ == "__main__":
    main()
