"""
Run the hybrid geometry + qualitative vision validation loop.

Usage:
    python scripts/run_hybrid_validation_loop.py --ppt ..\\HEB_Delivery_Status.pptx
    python scripts/run_hybrid_validation_loop.py --ppt deck.pptx --legacy-vision-measurement
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.pipeline import PipelineConfig, PipelineDependencies, PipelineMode, VisionLayoutPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hybrid pipeline: geometry inspect/correct + qualitative vision review."
    )
    parser.add_argument("--ppt", required=True, help="Path to .pptx")
    parser.add_argument("--content", default="", help="ppt_content.json (generate first)")
    parser.add_argument("--output", default="", help="Output .pptx when using --content")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--keep-images", action="store_true")
    parser.add_argument("--images-dir", default="")
    parser.add_argument(
        "--legacy-vision-measurement",
        action="store_true",
        help="Use legacy pixel-measurement vision loop (regression / comparison)",
    )
    parser.add_argument("--log", default="")
    parser.add_argument(
        "--geometry-only",
        action="store_true",
        help="Run geometry inspection only (no vision API calls)",
    )
    args = parser.parse_args()

    ppt_path = Path(args.ppt).resolve()
    content_json = Path(args.content) if args.content else None
    output_ppt = Path(args.output) if args.output else None

    mode = (
        PipelineMode.LEGACY_VISION_MEASUREMENT
        if args.legacy_vision_measurement
        else PipelineMode.HYBRID
    )

    if args.geometry_only:
        from app.geometry import GeometryInspector

        report = GeometryInspector().inspect(ppt_path)
        print(json.dumps(report.to_dict(), indent=2))
        out = Path(args.log) if args.log else ppt_path.with_suffix(".geometry_report.json")
        out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"Geometry report: {out}")
        raise SystemExit(0 if report.passes else 1)

    deps = PipelineDependencies.create_default(pipeline_mode=mode)
    pipeline = VisionLayoutPipeline(deps)
    config = PipelineConfig(
        max_iterations=args.max_iterations,
        keep_render_images=args.keep_images,
        render_output_dir=Path(args.images_dir) if args.images_dir else None,
    )

    result = pipeline.validate_and_correct(
        ppt_path=ppt_path if not content_json else None,
        content_json=content_json,
        output_ppt=output_ppt or ppt_path,
        config=config,
    )

    print(
        f"Pipeline ({mode.value}): {'PASS' if result.passed else 'INCOMPLETE'} "
        f"— {result.stopped_reason}"
    )
    print(f"Final deck: {result.final_presentation}")

    suffix = ".hybrid_loop.json" if mode == PipelineMode.HYBRID else ".vision_loop.json"
    out = Path(args.log) if args.log else result.final_presentation.with_suffix(suffix)
    out.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Log: {out}")

    raise SystemExit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
