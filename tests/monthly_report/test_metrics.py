from datetime import date

from monthly_report.data import SprintStories, month_bounds
from monthly_report.metrics import (
    ENDED,
    IN_PROGRESS,
    compute_sprint_metrics,
    sprint_display_status,
    story_category,
)

MEETING = date(2026, 8, 11)


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


def test_sprint_status_uses_db_value_variants():
    assert sprint_display_status("Ended", date(2026, 9, 1), MEETING) == ENDED
    assert sprint_display_status("ended", date(2026, 9, 1), MEETING) == ENDED
    assert sprint_display_status("In-progress", date(2026, 9, 1), MEETING) == IN_PROGRESS
    assert sprint_display_status("inprogress", date(2026, 9, 1), MEETING) == IN_PROGRESS


def test_sprint_finished_before_meeting_is_ended_even_if_db_says_inprogress():
    assert sprint_display_status("inprogress", date(2026, 8, 10), MEETING) == ENDED
    assert sprint_display_status("inprogress", date(2026, 8, 11), MEETING) == IN_PROGRESS


def test_ended_sprint_spill_over_is_in_review_plus_in_progress():
    sprint = _sprint(
        ["Done", "Done", "In Review", "In Progress", "To Do"],
        start=date(2026, 7, 28),
        end=date(2026, 8, 10),
    )
    metrics = compute_sprint_metrics(sprint, MEETING)
    assert metrics.status == ENDED
    assert metrics.total == 4  # To Do excluded from TC
    assert metrics.completed == 2
    assert metrics.spill_over == 2
    assert metrics.other == 1


def test_to_do_stories_are_excluded_from_tc():
    metrics = compute_sprint_metrics(
        _sprint(["To Do", "To Do", "Done", "In Progress"]),
        MEETING,
    )
    assert metrics.total == 2
    assert metrics.completed == 1
    assert metrics.in_progress == 1
    assert metrics.other == 2


def test_ended_sprint_without_unfinished_work_has_zero_spill_over():
    sprint = _sprint(["Done"], db_status="Ended")
    assert compute_sprint_metrics(sprint, MEETING).spill_over == 0


def test_in_progress_sprint_has_no_spill_over():
    metrics = compute_sprint_metrics(_sprint(["Done", "In Review", "In Progress"]), MEETING)
    assert metrics.status == IN_PROGRESS
    assert (metrics.total, metrics.completed, metrics.in_review, metrics.in_progress) == (3, 1, 1, 1)
    assert metrics.spill_over is None


def test_month_bounds():
    assert month_bounds(date(2026, 8, 11)) == (date(2026, 8, 1), date(2026, 8, 31))
    assert month_bounds(date(2028, 2, 3)) == (date(2028, 2, 1), date(2028, 2, 29))
