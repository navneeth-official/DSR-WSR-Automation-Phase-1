from datetime import date

import pytest
from pptx import Presentation

from monthly_report.accomplishments_slide import is_accomplishments_slide
from monthly_report.accomplishments_summarizer import (
    AccomplishmentsSummarizerError,
    AccomplishmentsSummary,
)
from monthly_report.config import resolve_template
from monthly_report.deck import ProjectSection, build_monthly_cadence_deck
from monthly_report.metrics import ENDED, SprintMetrics
from monthly_report.stories import StoryRecord
from monthly_report.tokens import iter_text_frames


def _all_text(slide):
    return [tf.text for tf in iter_text_frames(slide.shapes)]

try:
    TEMPLATE = resolve_template()
except FileNotFoundError:
    TEMPLATE = None

pytestmark = pytest.mark.skipif(
    TEMPLATE is None,
    reason="monthly template missing",
)


class _FakeSummarizer:
    def summarize(self, *, project_name: str, period_label: str, stories: list) -> AccomplishmentsSummary:
        return AccomplishmentsSummary(
            completed=(f"Completed work for {project_name}",),
            in_progress=("Ongoing validation",),
        )


class _PartialSummarizer:
    """First project only — simulates summarization failure for later projects."""

    def summarize(self, *, project_name: str, period_label: str, stories: list) -> AccomplishmentsSummary:
        if "LOCO" in project_name.upper():
            raise AccomplishmentsSummarizerError("simulated failure")
        return AccomplishmentsSummary(completed=(f"Done for {project_name}",), in_progress=())


def _sprint(name):
    return SprintMetrics(
        sprint_name=name,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 14),
        status=ENDED,
        db_status="Ended",
        total=3,
        completed=3,
        in_review=0,
        in_progress=0,
        other=0,
        spill_over=0,
    )


def test_accomplishments_slide_before_delivery(tmp_path):
    out = tmp_path / "deck.pptx"
    story = StoryRecord(
        jira_key="PRC-1",
        summary="Example story",
        title="Example title",
        description="Details",
        status="Done",
        sprint_name="S1",
        story_points=3.0,
        category="completed",
    )
    result = build_monthly_cadence_deck(
        TEMPLATE,
        out,
        [
            ProjectSection(
                project_key="PRC",
                title="Pricing Core",
                sprints=[_sprint("Alpha")],
                stories=(story,),
            )
        ],
        period_label="2026-06-01 to 2026-06-30",
        use_accomplishments=True,
        summarizer=_FakeSummarizer(),
    )

    assert result.accomplishments_slide_numbers == [2]
    assert result.delivery_slide_numbers == [3]

    prs = Presentation(str(out))
    acc_slide = prs.slides[1]
    del_slide = prs.slides[2]
    # Statement placeholders are consumed by the fill.
    assert not is_accomplishments_slide(acc_slide)
    body = "\n".join(_all_text(acc_slide))
    assert "Completed work for Pricing Core" in body
    assert "Ongoing validation" in body
    assert "(In progress)" not in body
    assert "Statement" not in body
    assert "Pricing Core" in del_slide.shapes.title.text


def test_delivery_not_filled_on_accomplishments_when_second_project_skips_acc(tmp_path):
    """Regression: orphan template Acc slide must not receive Delivery Updates fill."""
    out = tmp_path / "mixed.pptx"
    story = StoryRecord(
        jira_key="PRC-1",
        summary="Example",
        title="Example",
        description=None,
        status="Done",
        sprint_name="S1",
        story_points=None,
        category="completed",
    )
    result = build_monthly_cadence_deck(
        TEMPLATE,
        out,
        [
            ProjectSection(
                project_key="PRC",
                title="Pricing Core",
                sprints=[_sprint("A")],
                stories=(story,),
            ),
            ProjectSection(
                project_key="LOC",
                title="LOCO",
                sprints=[_sprint("B")],
                stories=(story,),
            ),
        ],
        period_label="2026-06-01 to 2026-06-30",
        use_accomplishments=True,
        summarizer=_PartialSummarizer(),
    )
    assert result.delivery_slide_numbers
    assert len(result.accomplishments_slide_numbers) == 1

    prs = Presentation(str(out))
    for number in result.accomplishments_slide_numbers:
        slide = prs.slides[number - 1]
        if any(shape.has_chart for shape in slide.shapes):
            pytest.fail("Accomplishments slide must not be filled as delivery (chart present)")
    assert not set(result.accomplishments_slide_numbers) & set(result.delivery_slide_numbers)
