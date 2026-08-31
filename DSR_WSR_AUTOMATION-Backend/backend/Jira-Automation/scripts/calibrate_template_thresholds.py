"""Calibrate layout evaluation thresholds from a measured WSR deck."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from app.paths import G10X_TEMPLATE
from app.services.ppt_format_extractor import extract_deck
from app.services.template_calibration import (
    APPROVED_DECK_PATH,
    calibrate_from_deck,
    format_calibration_report,
    save_thresholds,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate layout thresholds from a measured delivery-status deck."
    )
    parser.add_argument(
        "--ppt",
        default=str(APPROVED_DECK_PATH),
        help="Path to reference .pptx (default: output/HEB_Delivery_Status.pptx)",
    )
    parser.add_argument(
        "--out-report",
        default=str(_REPO / "output" / "debug" / "calibration_report.txt"),
        help="Write human-readable calibration report",
    )
    args = parser.parse_args()

    ppt = Path(args.ppt)
    if not ppt.is_file():
        fallback = G10X_TEMPLATE
        if not fallback.is_file():
            raise SystemExit(f"PPT not found: {ppt}")
        ppt = fallback

    deck = extract_deck(ppt)
    thresholds = calibrate_from_deck(deck)
    out = save_thresholds(thresholds)
    report = format_calibration_report(deck, thresholds)

    report_path = Path(args.out_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nWrote thresholds -> {out}")
    print(f"Wrote report     -> {report_path}")
    print(json.dumps(thresholds.to_dict(), indent=2))


if __name__ == "__main__":
    main()
