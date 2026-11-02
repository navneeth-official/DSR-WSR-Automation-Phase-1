"""
Build one monthly cadence PowerPoint for selected track(s) from PostgreSQL.

Independent of the weekly WSR pipeline (monthly_report/ + templates/monthly/ only).

Usage:
    python scripts/generate_monthly_report.py --meeting-date 2026-06-20 --track-name "Cost Core Service" --dry-run
    python scripts/generate_monthly_report.py --meeting-date 2026-06-20 --track-name "Cost Core Service"
    python scripts/generate_monthly_report.py --meeting-date 2026-06-20 --track-name "Cost Core Service" --track-name "Pricing Core"

One deck per run: Cover, Accomplishments + Delivery Updates for each project matched by
--track-name, then Thank you (Index slide is removed from the template).

Environment: MSR_MEETING_DATE, MSR_TRACK_NAME (comma-separated), MSR_TEMPLATE_PATH,
MSR_OUTPUT_DIR, MSR_ACCOMPLISHMENTS (auto|0|1);
LLM uses AZURE_OPENAI_MODEL (same as story titles)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from monthly_report.config import (
    default_output_path,
    project_display_name,
    project_order_keys,
    resolve_template,
)
from monthly_report.accomplishments_summarizer import accomplishments_enabled
from monthly_report.data import (
    list_projects_with_sprints_in_period,
    month_bounds,
    order_projects,
    sprints_in_period,
)
from monthly_report.stories import stories_in_period
from monthly_report.db import get_engine
from monthly_report.deck import ProjectSection, build_monthly_cadence_deck
from monthly_report.delivery_slide import format_schedule_date
from monthly_report.metrics import compute_sprint_metrics
from monthly_report.track_filter import filter_sections_by_track_names, parse_track_names


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _print_sprints(project_label: str, sprints) -> None:
    print(f"\n  [{project_label}]")
    if not sprints:
        print("    (no sprints with stories in this month)")
        return
    for number, sprint in enumerate(sprints, start=1):
        schedule = f"{format_schedule_date(sprint.start_date)} - {format_schedule_date(sprint.end_date)}"
        print(f"    Sprint {number}: {sprint.sprint_name}")
        print(f"      Schedule: {schedule}, {sprint.status}  (DB sprint_status: {sprint.db_status!r})")
        counts = (
            f"TC={sprint.total}  CC={sprint.completed}  RC={sprint.in_review}  "
            f"PC={sprint.in_progress}"
        )
        if sprint.spill_over is not None:
            counts += f"  SC={sprint.spill_over}"
        if sprint.other:
            counts += f"  (excluded from TC — To Do / other: {sprint.other})"
        print(f"      {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build one monthly cadence deck for project(s) selected by --track-name."
    )
    parser.add_argument(
        "--meeting-date",
        default=_env("MSR_MEETING_DATE") or date.today().isoformat(),
        help="Cadence meeting date (YYYY-MM-DD); fills cover {{Date}} and sets the report month",
    )
    parser.add_argument(
        "--track-name",
        action="append",
        dest="track_names",
        metavar="NAME",
        help=(
            "Project / track to include (display name, key, or fuzzy match). "
            "Repeat for multiple tracks, or comma-separate. Also MSR_TRACK_NAME."
        ),
    )
    parser.add_argument("--template", default="", help="Override monthly template .pptx")
    parser.add_argument("--output", default="", help="Output .pptx path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print sprint metrics for selected track(s); do not write PowerPoint",
    )
    parser.add_argument(
        "--no-accomplishments",
        action="store_true",
        help="Skip AI Accomplishments slides even when LLM credentials are configured",
    )
    args = parser.parse_args()

    meeting_date = date.fromisoformat(args.meeting_date)
    period_start, last_day = month_bounds(meeting_date)
    track_names = parse_track_names(args.track_names, _env("MSR_TRACK_NAME"))

    with get_engine().connect() as conn:
        projects = order_projects(
            list_projects_with_sprints_in_period(conn, period_start, last_day),
            project_order_keys(),
        )
        sections: list[ProjectSection] = []
        for project in projects:
            sprint_rows = sprints_in_period(conn, project.project_id, period_start, last_day)
            metrics = [compute_sprint_metrics(row, meeting_date) for row in sprint_rows]
            title = project_display_name(project.project_key, project.project_name)
            story_rows = stories_in_period(conn, project.project_id, period_start, last_day)
            sections.append(
                ProjectSection(
                    project_key=project.project_key,
                    title=title,
                    sprints=metrics,
                    stories=tuple(story_rows),
                )
            )

    filtered, track_warnings = filter_sections_by_track_names(sections, track_names)

    print(f"Meeting date: {meeting_date}")
    print(f"Report month: {period_start} to {last_day}")
    if track_names:
        print(f"Track filter: {', '.join(track_names)}")
    else:
        print("Track filter: (none — all projects with data)")
    print(f"Projects in deck: {len(filtered)} of {len(sections)} with data this month")
    acc_flag = "off" if args.no_accomplishments else ("on" if accomplishments_enabled() else "off (no LLM)")
    print(f"Accomplishments: {acc_flag}")
    for warning in track_warnings:
        print(f"Warning:      {warning}")

    for section in filtered:
        _print_sprints(f"{section.title} ({section.project_key})", section.sprints)

    if args.dry_run:
        return

    if not track_names:
        print(
            "Error: --track-name is required to build a deck (which project(s) to include).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not filtered:
        print("No matching projects with sprint data; nothing to build.", file=sys.stderr)
        raise SystemExit(1)

    template = resolve_template(args.template or None)
    output = Path(args.output) if args.output else default_output_path(meeting_date)

    period_label = f"{period_start.isoformat()} to {last_day.isoformat()}"
    result = build_monthly_cadence_deck(
        template,
        output,
        filtered,
        period_label=period_label,
        meeting_date=meeting_date,
        track_names=track_names,
        use_accomplishments=False if args.no_accomplishments else None,
    )

    print(f"\nTemplate:     {template}")
    print(f"Projects:     {', '.join(result.projects_included)}")
    for warning in result.warnings:
        print(f"Warning:      {warning}")
    if result.accomplishments_slide_numbers:
        print(f"Accomplishments slides: {result.accomplishments_slide_numbers}")
    if result.delivery_slide_numbers:
        print(f"Delivery slides: {result.delivery_slide_numbers}")
    for slide_number, tokens in result.leftover_tokens.items():
        print(f"Warning: slide {slide_number} unfilled placeholders: {tokens}")
    print(f"Built -> {output.resolve()}")


if __name__ == "__main__":
    main()
