"""
Unified WSR deck evaluation against a template in templates/.

One command covers:
  - Typography vs template (font, size, bold, line spacing)
  - Bullet format (category headers, story bullets)
  - HL/KA container waste (top, bottom, under-utilization)
  - Layout geometry (footer, HL–KA gap, overlap)
  - Visual AI review (default full mode; skip with --no-visual)

Outputs (default, under output/):
  - <deck>.format_eval.txt / .json     — business-readable score + per-slide summary
  - <deck>.format_eval.internal.json   — developer metrics
  - validation_report.md / .json       — CI-style checklist (typography + layout + waste)
  - validation/*.png                   — annotated slides (with --annotate)

Usage:
    python scripts/evaluate_ppt_format.py --ppt output/HEB_Delivery_Status.pptx
    python scripts/evaluate_ppt_format.py --ppt output/HEB_Delivery_Status.pptx --annotate
    python scripts/evaluate_ppt_format.py --ppt output/HEB_Delivery_Status.pptx --mode deterministic --no-visual
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.paths import (  # noqa: E402
    DEFAULT_CONTENT_JSON,
    evaluation_ai_report_paths,
    evaluation_report_paths,
)
from app.services.ppt_format_reference import resolve_evaluation_template  # noqa: E402
from app.services.ppt_format_report import (  # noqa: E402
    DeckFormatReport,
    annotate_evaluation_report,
    evaluate_ppt_format,
    save_evaluation_reports,
    write_validation_companion_reports,
)
from app.services.ppt_format_user_report import format_evaluation_for_terminal  # noqa: E402


def _print_evaluation_summary(report: DeckFormatReport) -> None:
    score = report.final_score or report.deck_score or report.deterministic_score
    score_text = f"{score:.1f}/100" if score is not None else "n/a"
    failed = sum(1 for s in report.slides if not s.passed)
    print(
        f"Evaluation: {'PASS' if report.deck_pass else 'FAIL'} "
        f"(score {score_text}, {failed} slide(s) failed)"
    )


def _print_saved_report_paths(
    *,
    report_path: Path,
    json_path: Path,
    internal_path: Path,
    ai_report_path: Path,
    ai_json_path: Path,
    include_visual: bool,
) -> None:
    print("Reports saved:")
    print(f"  Text report  -> {report_path}")
    print(f"  JSON report    -> {json_path}")
    if include_visual:
        print(f"  AI visual text -> {ai_report_path}")
        print(f"  AI visual JSON -> {ai_json_path}")
    print(f"  Internal log   -> {internal_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Unified WSR deck evaluation: template typography & bullets, HL/KA container "
            "waste, layout geometry, and optional visual AI review — one command."
        )
    )
    parser.add_argument(
        "--ppt",
        required=True,
        help="Path to .pptx deck (e.g. output/HEB_Delivery_Status.pptx)",
    )
    parser.add_argument(
        "--template",
        default="",
        help=(
            "Optional override reference WSR template .pptx. "
            "Default: templates/wsr_template.pptx, else newest .pptx in templates/"
        ),
    )
    parser.add_argument(
        "--content",
        default="",
        help=f"Optional ppt_content.json (default when present: {DEFAULT_CONTENT_JSON.name})",
    )
    parser.add_argument(
        "--mode",
        choices=("full", "ai", "deterministic", "visual"),
        default="full",
        help=(
            "full = deterministic + visual (default); "
            "deterministic = measurable layout only; "
            "visual = subjective visual review only; "
            "ai = deprecated legacy rulebook auditor"
        ),
    )
    parser.add_argument(
        "--all-slides",
        action="store_true",
        help="Include untouched G10X template placeholder slides (default: content scope only)",
    )
    parser.add_argument(
        "--no-visual",
        action="store_true",
        help="Skip visual AI review in full mode (deterministic only)",
    )
    parser.add_argument(
        "--vision",
        action="store_true",
        help="Deprecated alias for visual review (enabled by default in full mode)",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="JSON report path (default: output/<deck>.format_eval.json)",
    )
    parser.add_argument(
        "--report-out",
        default="",
        help="Human-readable report path (default: output/<deck>.format_eval.txt)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print full report to terminal only; do not write report files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also print the full report to the terminal (files are still saved by default)",
    )
    parser.add_argument(
        "--images-dir",
        default="",
        help="Directory for rendered slide PNGs (visual/full modes)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress raw vision API logs on the terminal (still written to vision_api_*.log)",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help=(
            "Export annotated PNGs for all deterministic findings "
            "(typography, bullets, unused HL/KA space) under output/validation/"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print developer report with rule IDs and measurements (default: user-facing report)",
    )
    args = parser.parse_args()

    ppt_path = Path(args.ppt).resolve()
    if not ppt_path.is_file():
        print(f"Error: file not found: {ppt_path}", file=sys.stderr)
        sys.exit(2)

    try:
        template_path = resolve_evaluation_template(args.template or None)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    content_json: Path | None
    if args.content:
        content_json = Path(args.content).resolve()
    elif DEFAULT_CONTENT_JSON.is_file():
        content_json = DEFAULT_CONTENT_JSON.resolve()
    else:
        content_json = None

    images_dir = Path(args.images_dir).resolve() if args.images_dir else None

    include_visual = not args.no_visual
    if args.vision:
        include_visual = True

    report = evaluate_ppt_format(
        ppt_path,
        template_path=template_path,
        mode=args.mode,
        content_json=content_json,
        scope_all_slides=args.all_slides,
        images_dir=images_dir,
        include_visual=include_visual,
        quiet_vision_log=args.quiet,
    )

    terminal_text = format_evaluation_for_terminal(report, debug=args.debug)

    if args.no_save:
        print(terminal_text)
        validation_json, validation_md = write_validation_companion_reports(
            report,
            ppt_path,
            output_dir=ppt_path.parent,
            content_json=content_json,
        )
        print(f"Validation report -> {validation_md}")
        if args.annotate:
            annotation_dir = annotate_evaluation_report(
                report,
                ppt_path,
                output_dir=ppt_path.parent / "validation",
            )
            print(f"Annotated images: {annotation_dir}")
    else:
        default_json, default_report, default_internal = evaluation_report_paths(ppt_path)
        default_ai_json, default_ai_report = evaluation_ai_report_paths(ppt_path)
        json_path = Path(args.json_out).resolve() if args.json_out else default_json
        report_path = Path(args.report_out).resolve() if args.report_out else default_report
        save_evaluation_reports(
            report,
            json_path=json_path,
            report_path=report_path,
            internal_json_path=default_internal,
            ai_json_path=default_ai_json,
            ai_report_path=default_ai_report,
        )
        validation_json, validation_md = write_validation_companion_reports(
            report,
            ppt_path,
            output_dir=ppt_path.parent,
            content_json=content_json,
        )
        if args.verbose:
            print(terminal_text)
            print()
        else:
            _print_evaluation_summary(report)
            if report.template_file:
                print(f"Reference template: {report.template_file}")
        _print_saved_report_paths(
            report_path=report_path,
            json_path=json_path,
            internal_path=default_internal,
            ai_report_path=default_ai_report,
            ai_json_path=default_ai_json,
            include_visual=include_visual,
        )
        print(f"  Validation MD   -> {validation_md}")
        print(f"  Validation JSON -> {validation_json}")
        if args.annotate:
            annotation_dir = annotate_evaluation_report(
                report,
                ppt_path,
                output_dir=ppt_path.parent / "validation",
            )
            print(f"  Annotated PNGs  -> {annotation_dir}")

    sys.exit(0 if report.deck_pass else 1)


if __name__ == "__main__":
    main()
