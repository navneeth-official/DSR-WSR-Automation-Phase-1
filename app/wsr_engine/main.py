"""WSR engine orchestrator and CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from app.services.ppt_cover_date import (
    find_cover_date_shape,
    format_cover_date,
    sync_cover_slide_wsr_date,
)
from app.services.ppt_logo_sync import resolve_logo_reference_slide, sync_all_delivery_slide_logos
from app.services.template_profile import clone_prototype_service_profile
from app.wsr_engine.content_parser import load_content
from app.wsr_engine.models import BuildReport, TitleFormat
from app.wsr_engine.ppt_writer import PptWriter
from app.wsr_engine.project_deletion import (
    delete_unmatched_projects,
    refresh_project_maps_after_deletion,
)
from app.wsr_engine.project_matcher import load_aliases, match_content_driven, match_projects
from app.wsr_engine.slide_order import (
    cleanup_orphan_contd_slides,
    delete_unmatched_delivery_slides,
    finalize_slide_order,
)
from app.wsr_engine.slide_provisioner import provision_project_slides
from app.wsr_engine.template_analyzer import analyze_template
from app.wsr_engine.template_mode import is_skeleton_template

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
        skeleton_mode = is_skeleton_template(template)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        writer = PptWriter(template_path, working_path=out)
        writer.prepare(template)

        if skeleton_mode:
            title_format = template.title_format or TitleFormat(
                prefix="Delivery status",
                separator=" \u2013 ",
                contd_marker="(Contd...)",
            )
            prototype = template.projects[0]
            projects = provision_project_slides(
                writer.prs,
                prototype.main_slide_index,
                content.projects,
                title_format,
                aliases,
            )
            template.projects = projects
            template.profile = clone_prototype_service_profile(
                template.profile,
                prototype.project_name,
                projects,
            )
            writer.template_model = template

            matched = match_content_driven(projects, content.projects, aliases)
            matched_names = set(matched.keys())
            report.detected_projects = len(projects)
            report.matched_projects = len(matched)
            report.deleted_projects = 0
            remaining_names = [p.project_name for p in projects if p.project_name in matched_names]
            projects = [p for p in projects if p.project_name in matched_names]
        else:
            matched = match_projects(template, content.projects, aliases)
            matched_names = set(matched.keys())
            report.detected_projects = len(template.projects)
            report.matched_projects = len(matched)

            deleted = delete_unmatched_projects(writer.prs, template, matched_names)
            deleted += delete_unmatched_delivery_slides(writer.prs, matched_names)
            report.deleted_projects = len(template.projects) - len(matched_names)
            if deleted:
                logger.info("Deleted %d slide(s) for unmatched projects", deleted)

            remaining_names = [
                p.project_name for p in template.projects if p.project_name in matched_names
            ]
            projects = refresh_project_maps_after_deletion(writer.prs, remaining_names)

        content_labels = {
            name: matched[name].title for name in matched if name in matched_names
        }

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
        if not skeleton_mode:
            delete_unmatched_delivery_slides(writer.prs, matched_names)

        projects = refresh_project_maps_after_deletion(writer.prs, remaining_names)
        report.index_entries_updated = writer.update_index(
            projects,
            skeleton_mode=skeleton_mode,
            content_labels=content_labels,
        )

        if content.report_end_date:
            end = date.fromisoformat(content.report_end_date)
            if sync_cover_slide_wsr_date(writer.prs, end):
                _, profile = find_cover_date_shape(writer.prs.slides[0])
                shown = format_cover_date(end, profile) if profile else end.isoformat()
                logger.info("Updated cover slide date -> %s", shown)
            else:
                logger.warning("Cover slide date placeholder not found")

        from app.wsr_engine.slide_ops import normalize_slide_partnames

        logo_ref = resolve_logo_reference_slide(writer.template_prs, template.projects)
        if logo_ref is not None:
            synced = sync_all_delivery_slide_logos(writer.prs, logo_ref)
            if synced:
                logger.info("Synced header logos on %d delivery slide(s)", synced)

        normalize_slide_partnames(writer.prs)
        if not skeleton_mode:
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
