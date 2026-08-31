from datetime import date

from app.schemas.jira_story import JiraStorySaveRequest


def test_save_request_normalizes_jira_timestamps() -> None:
    body = JiraStorySaveRequest(
        jira_key="PRICE-2972",
        summary="Test story",
        track="PRICE",
        status="In Progress",
        date_assigned="2026-06-01T13:34:39.968-0500",
        updated_date="2026-07-24T08:50:46.399-0500",
        snapshot_date="2026-07-27",
        sprint_start_date="2026-07-17",
        sprint_end_date="2026-07-31T23:59:59.000-0500",
    )
    assert body.date_assigned == date(2026, 6, 1)
    assert body.updated_date == date(2026, 7, 24)
    assert body.snapshot_date == date(2026, 7, 27)
    assert body.sprint_start_date == date(2026, 7, 17)
    assert body.sprint_end_date == date(2026, 7, 31)
