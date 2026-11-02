"""
Generate PPT delivery-status content from PostgreSQL and optionally build the deck.

Usage:
    python scripts/generate_ppt_content.py --start-date 2026-06-09 --end-date 2026-06-13
    python scripts/generate_ppt_content.py --start-date 2026-06-09 --end-date 2026-06-13 --save-titles
    python scripts/generate_ppt_content.py --start-date 2026-06-09 --end-date 2026-06-13 --json-only

Template: omit --template to use the newest .pptx in templates/ (or templates/wsr_template.pptx).

Environment (see .env.example — CLI flags override .env when both are set):

    WSR_REPORT_START_DATE=2026-04-16
    WSR_REPORT_END_DATE=2026-06-15
    WSR_PPT_ENGINE=v2
    WSR_PPT_OUTPUT=output/HEB_Delivery_Status.pptx

Minimal run when .env is configured:

    python scripts/generate_ppt_content.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")

from app.database import SessionLocal
from app.services.ppt_content_builder import build_ppt_content
from app.services.ppt_content_preview import format_content_preview

from app.paths import (
    DEFAULT_CONTENT_JSON,
    DEFAULT_CONTENT_PREVIEW,
    DEFAULT_PPT_OUTPUT,
    OUTPUT_DIR,
    PPT_BUILDER,
    REPO_ROOT,
    ensure_output_dir,
)
from app.services.wsr_template import resolve_wsr_template

DEFAULT_JSON = DEFAULT_CONTENT_JSON
DEFAULT_PREVIEW = DEFAULT_CONTENT_PREVIEW
DEFAULT_PPT = DEFAULT_PPT_OUTPUT


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def build_ppt_deck(
    content_json: Path,
    ppt_output: Path,
    layout_hints: Path | None = None,
    template: Path | str | None = None,
    engine: str = "v1",
) -> None:
    """Build PowerPoint deck using v1 (legacy) or v2 (template-agnostic WSR engine)."""
    ensure_output_dir()

    if engine == "v2":
        tpl = resolve_wsr_template(template)
        from app.wsr_engine.main import WsrEngine

        print(f"\n>> Building PowerPoint (WSR engine v2): {ppt_output}")
        print(f"   Template: {tpl}")
        report = WsrEngine().run(
            template_path=tpl,
            content_path=content_json,
            output_path=ppt_output,
        )
        for line in report.summary_lines():
            print(f"   {line}")
        if report.errors:
            raise RuntimeError(f"WSR engine errors: {report.errors}")
        return

    if not PPT_BUILDER.is_file():
        raise FileNotFoundError(f"PPT builder not found: {PPT_BUILDER}")
    tpl = resolve_wsr_template(template)
    if not tpl.is_file():
        raise FileNotFoundError(f"WSR template not found: {tpl}")

    cmd = [
        sys.executable,
        str(PPT_BUILDER),
        "--content",
        str(content_json.resolve()),
        "--output",
        str(ppt_output.resolve()),
    ]
    if layout_hints and layout_hints.is_file():
        cmd.extend(["--layout-hints", str(layout_hints.resolve())])
    print(f"\n>> Building PowerPoint: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build WSR PPT content from DB, write preview files, and build deck."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=_env("WSR_REPORT_START_DATE"),
        help="WSR report period start (YYYY-MM-DD). Default: WSR_REPORT_START_DATE in .env",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=_env("WSR_REPORT_END_DATE"),
        help="WSR report period end (YYYY-MM-DD). Default: WSR_REPORT_END_DATE in .env",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=_env("WSR_CONTENT_JSON") or str(DEFAULT_JSON),
        help=f"Output JSON path (default: WSR_CONTENT_JSON or {DEFAULT_JSON.name})",
    )
    parser.add_argument(
        "--preview",
        type=str,
        default=_env("WSR_CONTENT_PREVIEW") or str(DEFAULT_PREVIEW),
        help=f"Preview file (default: WSR_CONTENT_PREVIEW or {DEFAULT_PREVIEW.name})",
    )
    parser.add_argument(
        "--ppt-output",
        type=str,
        default=_env("WSR_PPT_OUTPUT") or str(DEFAULT_PPT),
        help=f"Output PowerPoint path (default: WSR_PPT_OUTPUT or {DEFAULT_PPT.name})",
    )
    parser.add_argument(
        "--template",
        type=str,
        default="",
        help=(
            "Optional override WSR template .pptx. "
            "Default: templates/wsr_template.pptx, else newest .pptx in templates/"
        ),
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=("v1", "v2"),
        default=_env("WSR_PPT_ENGINE") or "v2",
        help="Deck builder (default: WSR_PPT_ENGINE in .env, else v2)",
    )
    parser.add_argument(
        "--save-titles",
        action="store_true",
        help="Persist generated titles to jira_stories.title",
    )
    parser.add_argument(
        "--regenerate-titles",
        action="store_true",
        help="Re-call GPT even when title already exists in DB",
    )
    parser.add_argument(
        "--no-merge-titles",
        action="store_true",
        help="Keep separate chunks per project/sprint (do not merge by slide title)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only write JSON + preview; do not build PowerPoint (or WSR_JSON_ONLY=true in .env)",
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Run post-build spacing/layout repair loop after deck build",
    )
    parser.add_argument(
        "--max-fix-rounds",
        type=int,
        default=5,
        help="Max repair rounds when --auto-fix (default: 5)",
    )
    parser.add_argument(
        "--fix-min-score",
        type=float,
        default=85,
        help="Repair loop pass threshold for AI eval score (default: 85)",
    )
    parser.add_argument(
        "--vision-validate",
        action="store_true",
        help="Run hybrid validation loop after deck build (geometry + qualitative vision; default)",
    )
    parser.add_argument(
        "--vision-max-iterations",
        type=int,
        default=3,
        help="Max vision validation iterations (default: 3)",
    )
    parser.add_argument(
        "--vision-keep-images",
        action="store_true",
        help="Keep rendered slide PNGs from the vision loop",
    )
    parser.add_argument(
        "--vision-legacy-corrector",
        action="store_true",
        help="Use rulebook repair as the layout corrector in the vision loop",
    )
    parser.add_argument(
        "--legacy-vision-measurement",
        action="store_true",
        help="Use legacy pixel-measurement vision loop instead of hybrid (default)",
    )
    args = parser.parse_args()

    if not args.start_date or not args.end_date:
        print(
            "Error: report period required. Set WSR_REPORT_START_DATE and "
            "WSR_REPORT_END_DATE in .env, or pass --start-date and --end-date.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not args.json_only and _env("WSR_JSON_ONLY").lower() in ("1", "true", "yes"):
        args.json_only = True

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    db = SessionLocal()
    try:
        content = build_ppt_content(
            db,
            start_date=start_date,
            end_date=end_date,
            save_titles=args.save_titles,
            merge_titles=not args.no_merge_titles,
            regenerate_titles=args.regenerate_titles,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
    finally:
        db.close()

    json_path = Path(args.output)
    preview_path = Path(args.preview)
    ppt_path = Path(args.ppt_output)

    ensure_output_dir()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)

    preview_text = format_content_preview(content)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(preview_text)

    meta = content["meta"]
    print(f"Wrote JSON:    {json_path.resolve()}")
    print(f"Wrote preview: {preview_path.resolve()}")
    print(f"  report period: {content['report_start_date']} – {content['report_end_date']}")
    print(f"  stories:       {meta['story_count']}")
    print(f"  slides:        {meta['slide_count']}")
    print(f"  titles new:    {meta['titles_generated']}")
    print(f"  titles reused: {meta['titles_reused']}")
    if meta["titles_reused"] and not args.regenerate_titles:
        print(
            "  (titles already in DB — use --regenerate-titles to call GPT again)"
        )
    for slide in content["slides"]:
        sections = slide.get("sections") or [slide]
        n = sum(
            len(s.get("released", []))
            + len(s.get("inprogress", []))
            + len(s.get("completed", []))
            for s in sections
        )
        sprint_label = ", ".join(s["sprint_name"] for s in sections)
        print(f"  - {slide['title']}: {n} stories ({sprint_label})")

    if not args.json_only:
        if args.vision_validate:
            from app.pipeline import PipelineConfig, PipelineDependencies, PipelineMode, VisionLayoutPipeline

            print("\n>> Generating deck and running validation loop...")
            mode = (
                PipelineMode.LEGACY_VISION_MEASUREMENT
                if args.legacy_vision_measurement
                else PipelineMode.HYBRID
            )
            print(f"   Pipeline mode: {mode.value}")
            deps = PipelineDependencies.create_default(
                use_legacy_corrector=args.vision_legacy_corrector,
                pipeline_mode=mode,
            )
            pipeline = VisionLayoutPipeline(deps)
            config = PipelineConfig(
                max_iterations=args.vision_max_iterations,
                keep_render_images=args.vision_keep_images,
            )
            suffix = (
                ".vision_loop.json"
                if mode == PipelineMode.LEGACY_VISION_MEASUREMENT
                else ".hybrid_loop.json"
            )
            loop_path = OUTPUT_DIR / f"{ppt_path.stem}{suffix}"
            ppt_path, loop_result = pipeline.generate_validate(
                json_path,
                ppt_path,
                run_validation=True,
                config=config,
                validation_log=loop_path,
            )
            if loop_result:
                status = "PASSED" if loop_result.passed else "INCOMPLETE"
                print(
                    f"Validation loop ({mode.value}) {status} ({loop_result.stopped_reason}, "
                    f"{len(loop_result.iteration_history)} iteration(s)) -> {loop_path}"
                )
                print(f"Built -> {ppt_path.resolve()}")
        else:
            build_ppt_deck(
                json_path,
                ppt_path,
                template=args.template.strip() or None,
                engine=args.engine,
            )
            print(f"\nBuilt -> {ppt_path.resolve()}")

        if args.auto_fix and not args.vision_validate:
            from app.services.ppt_format_repair_loop import repair_deck_until_pass

            print("\n>> Running post-build layout repair...")
            repair_result = repair_deck_until_pass(
                ppt_path,
                json_path,
                max_rounds=args.max_fix_rounds,
                pass_threshold=args.fix_min_score,
            )
            status = "PASSED" if repair_result.passed else "INCOMPLETE"
            print(f"Auto-fix {status} — log: {repair_result.repair_log_path}")
            if repair_result.final_evaluation:
                from app.paths import evaluation_report_paths

                ev = repair_result.final_evaluation
                eval_json_path, eval_report_path, _ = evaluation_report_paths(ppt_path)
                eval_json_path.write_text(
                    json.dumps(ev, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                lines = [
                    f"Deck: {ppt_path}",
                    f"Score: {ev.get('deck_score')}/100",
                    f"Result: {'PASS' if ev.get('deck_pass') else 'FAIL'}",
                ]
                for issue in ev.get("critical_issues") or []:
                    lines.append(f"  - {issue}")
                eval_report_path.write_text("\n".join(lines), encoding="utf-8")
                print(
                    f"Format eval: {ev.get('deck_score')}/100 "
                    f"({'PASS' if ev.get('deck_pass') else 'FAIL'}) -> {eval_json_path}"
                )
                print(f"Text report  -> {eval_report_path}")

        print(f"\nDone -> {ppt_path.resolve()}")


if __name__ == "__main__":
    main()
