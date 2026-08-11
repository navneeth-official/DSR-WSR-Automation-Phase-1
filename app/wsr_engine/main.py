"""WSR engine orchestrator and CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.wsr_engine.content_parser import load_content
from app.wsr_engine.models import BuildReport
from app.wsr_engine.project_deletion import (
    delete_unmatched_projects,
    refresh_project_maps_after_deletion,
)
from app.wsr_engine.project_matcher import load_aliases, match_projects
from app.wsr_engine.ppt_writer import PptWriter, sync_cover_slide_wsr_date
from app.wsr_engine.slide_order import (
    cleanup_orphan_contd_slides,
    delete_unmatched_delivery_slides,
    finalize_slide_order,
)
from app.wsr_engine.template_analyzer import analyze_template

logger = logging.getLogger(__name__)


class WsrEngine:
    def run(
        self,
        template_path: Path | str,
        content_path: Path | str,
        output_path: Path | str,
        aliases_path: Path | str | None = None,
    ) -> BuildReport:
        report = BuildReport()

        template = analyze_template(template_path)
        content = load_content(content_path)
        aliases = load_aliases(aliases_path)

        report.detected_projects = len(template.projects)
        matched = match_projects(template, content.projects, aliases)
        report.matched_projects = len(matched)
        matched_names = set(matched.keys())

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        writer = PptWriter(template_path, working_path=out)
        writer.prepare(template)

        deleted = delete_unmatched_projects(writer.prs, template, matched_names)
        deleted += delete_unmatched_delivery_slides(writer.prs, matched_names)
        unmatched_count = len(template.projects) - len(matched_names)
        report.deleted_projects = unmatched_count
        if deleted:
            logger.info("Deleted %d slide(s) for unmatched projects", deleted)

        remaining_names = [
            p.project_name for p in template.projects if p.project_name in matched_names
        ]
        projects = refresh_project_maps_after_deletion(writer.prs, remaining_names)

        for proj in projects:
            content_proj = matched.get(proj.project_name)
            if content_proj is None:
                continue
            print(f"   Filling: {proj.project_name}...", flush=True)
            try:
                writer.apply_project(proj, content_proj, template.profile, report)
            except Exception as exc:
                msg = f"Failed to fill {proj.project_name}: {exc}"
                logger.exception(msg)
                report.errors.append(msg)

        finalize_slide_order(writer.prs, remaining_names)
        cleanup_orphan_contd_slides(writer.prs)
        delete_unmatched_delivery_slides(writer.prs, matched_names)

        projects = refresh_project_maps_after_deletion(writer.prs, remaining_names)
        report.index_entries_updated = writer.update_index(projects)

        if content.report_start_date:
            sync_cover_slide_wsr_date(writer.prs, content.report_start_date)

        from app.wsr_engine.slide_ops import normalize_slide_partnames

        normalize_slide_partnames(writer.prs)
        delete_unmatched_delivery_slides(writer.prs, matched_names)

        saved = writer.save(out)
        report.output_path = str(saved)

        for line in report.summary_lines():
            logger.info(line)

        return report


def _configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build WSR PowerPoint (template-agnostic engine v2)")
    parser.add_argument("--template", required=True, help="WSR template .pptx")
    parser.add_argument("--content", required=True, help="ppt_content.json path")
    parser.add_argument("--output", required=True, help="Output .pptx path")
    parser.add_argument("--aliases", default="", help="Optional wsr_aliases.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    engine = WsrEngine()
    report = engine.run(
        template_path=args.template,
        content_path=args.content,
        output_path=args.output,
        aliases_path=args.aliases or None,
    )

    for line in report.summary_lines():
        print(line)

    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
