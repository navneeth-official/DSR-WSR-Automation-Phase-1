"""Validate a generated WSR deck — thin wrapper around the unified evaluator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paths import DEFAULT_CONTENT_JSON  # noqa: E402
from app.services.ppt_format_reference import resolve_evaluation_template  # noqa: E402
from app.services.ppt_format_report import (  # noqa: E402
    evaluate_ppt_format,
    write_validation_companion_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a WSR deck (typography + layout + container waste). "
            "Prefer: python scripts/evaluate_ppt_format.py for the full unified evaluation."
        )
    )
    parser.add_argument("--ppt", required=True, help="Path to generated .pptx")
    parser.add_argument(
        "--template",
        default="",
        help="Optional override reference WSR template (default: newest .pptx in templates/)",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for validation_report.* (default: same folder as deck)",
    )
    parser.add_argument(
        "--no-annotate",
        action="store_true",
        help="Skip exporting annotated PNG evidence under <output-dir>/validation/",
    )
    parser.add_argument(
        "--no-rendered-bounds",
        action="store_true",
        help="Deprecated — kept for CLI compatibility (bounds always measured when possible)",
    )
    args = parser.parse_args()
    _ = args.no_rendered_bounds

    ppt = Path(args.ppt).resolve()
    if not ppt.is_file():
        print(f"Deck not found: {ppt}", file=sys.stderr)
        return 2

    try:
        template = resolve_evaluation_template(args.template or None)
    except FileNotFoundError as exc:
        print(f"Template not found: {exc}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).resolve() if args.output_dir else ppt.parent
    content_json = DEFAULT_CONTENT_JSON.resolve() if DEFAULT_CONTENT_JSON.is_file() else None

    report = evaluate_ppt_format(
        ppt,
        template_path=template,
        mode="deterministic",
        content_json=content_json,
        include_visual=False,
    )
    report_json, report_md = write_validation_companion_reports(
        report,
        ppt,
        output_dir=output_dir,
        content_json=content_json,
        annotate=not args.no_annotate,
    )

    fail_count = sum(
        1
        for slide in report.slides
        for v in slide.violations
        if v.get("source") == "deterministic" and v.get("severity") in {"critical", "major"}
    )
    warn_count = sum(
        1
        for slide in report.slides
        for v in slide.violations
        if v.get("source") == "deterministic" and v.get("severity") == "minor"
    )
    print(f"deck_pass={report.deck_pass}")
    print(f"findings={sum(len(s.violations) for s in report.slides)} fail={fail_count} warn={warn_count}")
    print(f"Wrote {report_json}")
    print(f"Wrote {report_md}")
    if not args.no_annotate:
        print(f"Annotated images: {output_dir / 'validation'}")
    print(
        "Tip: run scripts/evaluate_ppt_format.py (default full mode) for "
        "typography + layout + visual AI in one step."
    )
    return 0 if report.deck_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
