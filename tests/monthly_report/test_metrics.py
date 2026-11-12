from datetime import date

from monthly_report.data import SprintStories, month_bounds
from monthly_report.metrics import (
    ENDED,
    IN_PROGRESS,
    compute_sprint_metrics,
    sprint_display_status,
    story_category,
)

PERIOD_START = date(2026, 8, 1)
PERIOD_END = date(2026, 8, 31)


def _sprint(statuses, *, db_status="inprogress", start=date(2026, 8, 11), end=date(2026, 8, 24)):
    return SprintStories(
        sprint_id=1,
        sprint_name="Q4.01 FY26 Cassiopeia",
        sprint_status=db_status,
        start_date=start,
        end_date=end,
        story_statuses=tuple(statuses),
    )


def test_story_category_normalizes_spelling():
    assert story_category("Done") == "completed"
    assert story_category("In Review") == "in_review"
    assert story_category("in-review") == "in_review"
    assert story_category("In-Progress") == "in_progress"
    assert story_category("To Do") == "other"
    assert story_category("todo") == "other"


def test_sprint_continuing_past_period_end_is_in_progress():
    assert (
        sprint_display_status(date(2026, 8, 20), date(2026, 9, 10), PERIOD_START, PERIOD_END)
        == IN_PROGRESS
    )


def test_sprint_ending_on_or_before_period_end_is_ended():
    assert (
        sprint_display_status(date(2026, 8, 1), date(2026, 8, 31), PERIOD_START, PERIOD_END)
        == ENDED
    )
    assert (
        sprint_display_status(date(2026, 8, 1), date(2026, 8, 10), PERIOD_START, PERIOD_END)
        == ENDED
    )
    assert (
        sprint_display_status(date(2026, 7, 28), date(2026, 8, 10), PERIOD_START, PERIOD_END)
        == ENDED
    )


def test_db_sprint_status_is_ignored():
    # Even if DB says "Ended", a sprint still active on period_end is In-Progress.
    sprint = _sprint(["Done"], db_status="Ended", start=date(2026, 8, 20), end=date(2026, 9, 5))
    assert compute_sprint_metrics(sprint, PERIOD_START, PERIOD_END).status == IN_PROGRESS


def test_ended_sprint_spill_over_is_in_review_plus_in_progress():
    sprint = _sprint(
        ["Done", "Done", "In Review", "In Progress", "To Do"],
        start=date(2026, 7, 28),
        end=date(2026, 8, 10),
    )
    metrics = compute_sprint_metrics(sprint, PERIOD_START, PERIOD_END)
    assert metrics.status == ENDED
    assert metrics.total == 4  # To Do excluded from TC
    assert metrics.completed == 2
    assert metrics.spill_over == 2
    assert metrics.other == 1


def test_to_do_stories_are_excluded_from_tc():
    metrics = compute_sprint_metrics(
        _sprint(["To Do", "To Do", "Done", "In Progress"]),
        PERIOD_START,
        PERIOD_END,
    )
    assert metrics.total == 2
    assert metrics.completed == 1
    assert metrics.in_progress == 1
    assert metrics.other == 2


def test_ended_sprint_without_unfinished_work_has_zero_spill_over():
    sprint = _sprint(
        ["Done"],
        db_status="inprogress",
        start=date(2026, 8, 1),
        end=date(2026, 8, 10),
    )
    assert compute_sprint_metrics(sprint, PERIOD_START, PERIOD_END).spill_over == 0


def test_in_progress_sprint_has_no_spill_over():
    metrics = compute_sprint_metrics(
        _sprint(
            ["Done", "In Review", "In Progress"],
            start=date(2026, 8, 20),
            end=date(2026, 9, 5),
        ),
        PERIOD_START,
        PERIOD_END,
    )
    assert metrics.status == IN_PROGRESS
    assert (metrics.total, metrics.completed, metrics.in_review, metrics.in_progress) == (3, 1, 1, 1)
    assert metrics.spill_over is None


def test_month_bounds():
    assert month_bounds(date(2026, 8, 11)) == (date(2026, 8, 1), date(2026, 8, 31))
    assert month_bounds(date(2028, 2, 3)) == (date(2028, 2, 1), date(2028, 2, 29))
