"""Validate a generated WSR deck and write human + CI reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.validation import validate_deck


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a WSR deck after build.")
    parser.add_argument("--ppt", required=True, help="Path to generated .pptx")
    parser.add_argument(
        "--template",
        required=True,
        help="Reference WSR template .pptx in templates/ (typography source of truth)",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for validation_report.* (default: same folder as deck)",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Export annotated PNGs under output/validation/",
    )
    parser.add_argument(
        "--no-rendered-bounds",
        action="store_true",
        help="Skip COM rendered HL bounds (faster, less precise HL waste)",
    )
    args = parser.parse_args()

    ppt = Path(args.ppt).resolve()
    if not ppt.is_file():
        print(f"Deck not found: {ppt}", file=sys.stderr)
        return 2

    template = Path(args.template).resolve()
    if not template.is_file():
        print(f"Template not found: {template}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).resolve() if args.output_dir else ppt.parent

    result = validate_deck(
        ppt,
        template_path=template,
        output_dir=output_dir,
        annotate=args.annotate,
        use_rendered_bounds=not args.no_rendered_bounds,
    )

    fail_count = sum(1 for f in result.findings if f.get("severity") == "fail")
    warn_count = sum(1 for f in result.findings if f.get("severity") == "warn")
    print(f"deck_pass={result.deck_pass}")
    print(f"findings={len(result.findings)} fail={fail_count} warn={warn_count}")
    print(f"Wrote {result.report_json}")
    print(f"Wrote {result.report_md}")
    if result.annotation_dir:
        print(f"Annotated images: {result.annotation_dir}")
    return 0 if result.deck_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
