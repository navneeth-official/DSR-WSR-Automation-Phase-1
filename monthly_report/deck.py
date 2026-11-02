"""Build one monthly cadence deck containing every project in report order."""

from __future__ import annotations

from dataclasses import dataclass, field
import tempfile
from datetime import date
from pathlib import Path
from typing import Literal

from pptx import Presentation

from monthly_report.cover_slide import fill_cover_slide
from monthly_report.accomplishments_slide import (
    fill_accomplishments_slide,
    find_accomplishments_slide,
    is_accomplishments_slide,
)
from monthly_report.accomplishments_summarizer import (
    AccomplishmentsSummarizer,
    AccomplishmentsSummarizerError,
    accomplishments_enabled,
    summarizer_config_from_env,
)
from monthly_report.delivery_slide import (
    analyze_delivery_slide,
    continuation_title,
    duplicate_delivery_slide,
    fill_delivery_slide,
    find_delivery_slide,
    is_delivery_slide,
)
from monthly_report.index_slide import find_index_slide_index
from monthly_report.metrics import SprintMetrics
from monthly_report.pptx_com import (
    com_available,
    materialize_slides_via_com,
    save_presentation,
)
from monthly_report.slide_ops import duplicate_slide, move_slide_before, remove_slide, slide_index
from monthly_report.stories import StoryRecord


@dataclass(frozen=True)
class ProjectSection:
    project_key: str
    title: str
    sprints: list[SprintMetrics]
    stories: tuple[StoryRecord, ...] = ()
    accomplishments_summary: object | None = None


@dataclass
class MonthlyDeckResult:
    output_path: Path
    projects_included: list[str] = field(default_factory=list)
    delivery_slide_numbers: list[int] = field(default_factory=list)
    accomplishments_slide_numbers: list[int] = field(default_factory=list)
    index_entries_updated: int = 0
    leftover_tokens: dict[int, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _SlideJob:
    kind: Literal["accomplishments", "delivery"]
    section: ProjectSection
    page_idx: int = 0
    page_sprints: tuple[SprintMetrics, ...] = ()


def _find_thank_you_slide(prs):
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame and "thank you" in shape.text_frame.text.lower():
                return slide
    return prs.slides[-1]


def _strip_index_slide(prs) -> None:
    """Monthly cadence decks omit the WSR-style Index slide."""
    index_idx = find_index_slide_index(prs)
    if index_idx is not None:
        remove_slide(prs, prs.slides[index_idx])


def _content_region_start(prs) -> int:
    """First slide index after cover (and index, if still present)."""
    index_idx = find_index_slide_index(prs)
    if index_idx is not None:
        return index_idx + 1
    return 1


def _remove_accomplishments_slides(prs) -> None:
    for slide in list(prs.slides):
        if is_accomplishments_slide(slide):
            remove_slide(prs, slide)


def _build_slide_jobs(
    sections: list[ProjectSection],
    *,
    per_slide: int,
    include_accomplishments: bool,
) -> list[_SlideJob]:
    jobs: list[_SlideJob] = []
    for section in sections:
        if not section.sprints:
            continue
        if include_accomplishments and section.accomplishments_summary is not None:
            jobs.append(_SlideJob("accomplishments", section))
        for page_idx in range(0, len(section.sprints), per_slide):
            chunk = section.sprints[page_idx : page_idx + per_slide]
            jobs.append(
                _SlideJob(
                    "delivery",
                    section,
                    page_idx=page_idx,
                    page_sprints=tuple(chunk),
                )
            )
    return jobs


def _source_indices_for_jobs(
    jobs: list[_SlideJob],
    acc_index: int,
    del_index: int,
) -> list[int]:
    indices: list[int] = []
    for job in jobs:
        indices.append(acc_index if job.kind == "accomplishments" else del_index)
    return indices


def _is_fillable_delivery_slide(slide) -> bool:
    """True when the slide has the chart and both sprint table prototypes."""
    if is_accomplishments_slide(slide):
        return False
    if not is_delivery_slide(slide):
        return False
    try:
        analyze_delivery_slide(slide)
    except ValueError:
        return False
    return True


def _content_slides_before_thank(prs, thank_index: int) -> tuple[list, list, list]:
    """Classify slides before Thank you into accomplishments, delivery, and unknown."""
    start = _content_region_start(prs)
    acc_slides: list = []
    delivery_slides: list = []
    unknown: list = []
    for idx in range(start, thank_index):
        slide = prs.slides[idx]
        if is_accomplishments_slide(slide):
            acc_slides.append(slide)
        elif _is_fillable_delivery_slide(slide):
            delivery_slides.append(slide)
        else:
            unknown.append(slide)
    return acc_slides, delivery_slides, unknown


def _match_slides_to_jobs(
    prs,
    jobs: list[_SlideJob],
    thank_index: int,
    warnings: list[str],
) -> list[tuple[object, _SlideJob]]:
    """
    Map COM-expanded slides to fill jobs by slide type, not deck position.

    The template keeps an Accomplishments slide even when the first project has no
    summary; positional zip would assign that slide to a Delivery job.
    """
    acc_pool, del_pool, unknown = _content_slides_before_thank(prs, thank_index)
    if unknown:
        warnings.append(
            f"Skipped {len(unknown)} unrecognized slide(s) before Thank you when matching jobs."
        )

    need_acc = sum(1 for job in jobs if job.kind == "accomplishments")
    need_del = sum(1 for job in jobs if job.kind == "delivery")
    if len(acc_pool) < need_acc or len(del_pool) < need_del:
        raise ValueError(
            f"Slide/job mismatch: need {need_acc} accomplishments and {need_del} delivery "
            f"slides, found {len(acc_pool)} and {len(del_pool)}."
        )

    for slide in acc_pool[need_acc:] + del_pool[need_del:]:
        remove_slide(prs, slide)
        thank_index -= 1

    acc_i = 0
    del_i = 0
    ordered: list[tuple[object, _SlideJob]] = []
    for job in jobs:
        if job.kind == "accomplishments":
            ordered.append((acc_pool[acc_i], job))
            acc_i += 1
        else:
            ordered.append((del_pool[del_i], job))
            del_i += 1
    return ordered


def _build_ordered_slides_python_pptx(
    prs,
    jobs: list[_SlideJob],
    *,
    acc_proto,
    delivery_proto,
    delivery_template,
    thank_you,
) -> list[tuple[object, _SlideJob]]:
    """Create or reuse slides in job order without PowerPoint COM."""
    acc_used = False
    del_used = False
    ordered: list[tuple[object, _SlideJob]] = []
    for job in jobs:
        if job.kind == "accomplishments":
            if acc_proto is None:
                raise ValueError("Accomplishments job but no Accomplishments slide in template")
            if not acc_used:
                slide = acc_proto
                acc_used = True
            else:
                slide = duplicate_slide(prs, acc_proto)
            ordered.append((slide, job))
        else:
            if not del_used:
                slide = delivery_proto
                del_used = True
            else:
                slide = duplicate_delivery_slide(prs, delivery_proto, delivery_template)
            ordered.append((slide, job))
    for slide, _job in ordered:
        move_slide_before(prs, slide, thank_you)
    return ordered


def _resolve_section_summary(
    section: ProjectSection,
    summarizer: AccomplishmentsSummarizer | None,
    period_label: str,
    warnings: list[str],
):
    if section.accomplishments_summary is not None:
        return section.accomplishments_summary
    if summarizer is None:
        return None
    try:
        return summarizer.summarize(
            project_name=section.title,
            period_label=period_label,
            stories=list(section.stories),
        )
    except AccomplishmentsSummarizerError as exc:
        warnings.append(f"{section.title}: accomplishments not generated ({exc}).")
        return None


def build_monthly_cadence_deck(
    template_path: Path,
    output_path: Path,
    sections: list[ProjectSection],
    *,
    index_reference_path: Path | None = None,
    period_label: str = "",
    meeting_date: date | None = None,
    track_names: list[str] | None = None,
    use_accomplishments: bool | None = None,
    summarizer: AccomplishmentsSummarizer | None = None,
) -> MonthlyDeckResult:
    """
    One deck: Cover, optional Accomplishments + Delivery Updates per project, then Thank you.
    """
    prs = Presentation(str(template_path))
    result = MonthlyDeckResult(output_path=output_path)

    track_names = list(track_names or [])
    cover_label = track_names[0].strip() if track_names else ""
    if meeting_date is not None:
        cover_leftovers = fill_cover_slide(
            prs.slides[0],
            track_name=cover_label,
            meeting_date=meeting_date,
        )
        if cover_leftovers:
            result.leftover_tokens[1] = cover_leftovers
        if not cover_label:
            result.warnings.append(
                "Cover slide track name not set; pass --track-name or MSR_TRACK_NAME."
            )

    _strip_index_slide(prs)
    _ = index_reference_path

    include_acc = accomplishments_enabled() if use_accomplishments is None else use_accomplishments
    acc_config = summarizer_config_from_env()
    active_summarizer = summarizer

    if include_acc:
        if active_summarizer is None:
            from monthly_report.accomplishments_summarizer import resolve_summarizer

            active_summarizer = resolve_summarizer()
        if active_summarizer is None:
            include_acc = False
            result.warnings.append(
                "Accomplishments slides skipped: enable MSR_ACCOMPLISHMENTS=1 and configure "
                "AZURE_OPENAI_* or OPENAI_API_KEY (optional MSR_ACCOMPLISHMENTS_MODEL)."
            )
    else:
        _remove_accomplishments_slides(prs)

    delivery_proto = find_delivery_slide(prs)
    delivery_template = analyze_delivery_slide(delivery_proto)
    chart_theme_colors = delivery_template.series_theme_colors
    per_slide = delivery_template.sprints_per_slide

    enriched: list[ProjectSection] = []
    for section in sections:
        if not section.sprints:
            continue
        result.projects_included.append(section.project_key)
        summary = None
        if include_acc:
            summary = _resolve_section_summary(
                section, active_summarizer, period_label, result.warnings
            )
            if summary is None:
                result.warnings.append(
                    f"{section.title}: no Accomplishments slide (missing stories or summarization failed)."
                )
        enriched.append(
            ProjectSection(
                project_key=section.project_key,
                title=section.title,
                sprints=section.sprints,
                stories=section.stories,
                accomplishments_summary=summary,
            )
        )

    include_acc = include_acc and any(s.accomplishments_summary for s in enriched)
    if not include_acc:
        _remove_accomplishments_slides(prs)

    jobs = _build_slide_jobs(
        enriched,
        per_slide=per_slide,
        include_accomplishments=include_acc,
    )

    thank_you = _find_thank_you_slide(prs)
    acc_proto = find_accomplishments_slide(prs) if include_acc else None

    if not jobs:
        remove_slide(prs, delivery_proto)
        if acc_proto is not None:
            remove_slide(prs, acc_proto)
        result.warnings.append("No project sprints in the report month; content slides removed.")
    else:
        acc_index = slide_index(prs, acc_proto) if acc_proto is not None else -1
        del_index = slide_index(prs, delivery_proto)
        thank_index = slide_index(prs, thank_you)

        # python-pptx slide/chart copy corrupts large decks; prefer PowerPoint COM.
        ordered_slides: list[tuple[object, _SlideJob]] | None = None
        if len(jobs) > 1 and com_available():
            with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
                staging = Path(tmp.name)
            try:
                prs.save(str(staging))
                try:
                    materialize_slides_via_com(
                        staging,
                        thank_index,
                        _source_indices_for_jobs(jobs, acc_index, del_index),
                    )
                    prs = Presentation(str(staging))
                    thank_you = _find_thank_you_slide(prs)
                    if include_acc:
                        acc_proto = find_accomplishments_slide(prs)
                    delivery_proto = find_delivery_slide(prs)
                    delivery_template = analyze_delivery_slide(delivery_proto)
                    chart_theme_colors = delivery_template.series_theme_colors
                    thank_index = slide_index(prs, thank_you)
                    ordered_slides = _match_slides_to_jobs(
                        prs, jobs, thank_index, result.warnings
                    )
                    thank_you = _find_thank_you_slide(prs)
                    for slide, _job in ordered_slides:
                        move_slide_before(prs, slide, thank_you)
                except Exception as exc:
                    prs = Presentation(str(template_path))
                    _strip_index_slide(prs)
                    thank_you = _find_thank_you_slide(prs)
                    if include_acc:
                        acc_proto = find_accomplishments_slide(prs)
                    delivery_proto = find_delivery_slide(prs)
                    delivery_template = analyze_delivery_slide(delivery_proto)
                    chart_theme_colors = delivery_template.series_theme_colors
                    ordered_slides = None
                    result.warnings.append(
                        f"PowerPoint slide duplication failed ({exc}); "
                        "using python-pptx copy — file may need Repair in PowerPoint."
                    )
            finally:
                staging.unlink(missing_ok=True)

        if ordered_slides is None:
            if len(jobs) > 1 and not com_available():
                result.warnings.append(
                    "Multiple content slides need PowerPoint (pywin32) on Windows; "
                    "using python-pptx copy — file may need Repair in PowerPoint."
                )
            ordered_slides = _build_ordered_slides_python_pptx(
                prs,
                jobs,
                acc_proto=acc_proto,
                delivery_proto=delivery_proto,
                delivery_template=delivery_template,
                thank_you=thank_you,
            )

        thank_you = _find_thank_you_slide(prs)
        for slide, job in ordered_slides:
            target_index = slide_index(prs, slide)

            if job.kind == "accomplishments":
                summary = job.section.accomplishments_summary
                if summary is None:
                    continue
                fill_accomplishments_slide(
                    slide,
                    project_title=job.section.title,
                    summary=summary,
                    max_lines=acc_config.max_slide_lines,
                )
                result.accomplishments_slide_numbers.append(target_index + 1)
                continue

            if not _is_fillable_delivery_slide(slide):
                raise ValueError(
                    f"Cannot fill Delivery Updates for {job.section.title!r} on slide "
                    f"{target_index + 1}: slide is not a valid delivery template "
                    f"(missing chart or sprint tables). "
                    f"If this persists, retry with --no-accomplishments and check warnings."
                )
            slide_number = target_index + 1
            result.delivery_slide_numbers.append(slide_number)
            leftovers = fill_delivery_slide(
                slide,
                continuation_title(job.section.title, job.page_idx),
                list(job.page_sprints),
                series_theme_colors=chart_theme_colors,
            )
            if leftovers:
                result.leftover_tokens[slide_number] = leftovers

    save_warning = save_presentation(output_path, prs)
    if save_warning:
        result.warnings.append(save_warning)
    return result


def build_monthly_deck(
    template_path: Path,
    output_path: Path,
    project_title: str,
    sprints: list[SprintMetrics],
    *,
    index_reference_path: Path | None = None,
    project_key: str = "PRC",
) -> MonthlyDeckResult:
    """Convenience wrapper for tests: one project in the combined deck."""
    return build_monthly_cadence_deck(
        template_path,
        output_path,
        [ProjectSection(project_key=project_key, title=project_title, sprints=sprints)],
        index_reference_path=index_reference_path,
        use_accomplishments=False,
    )
