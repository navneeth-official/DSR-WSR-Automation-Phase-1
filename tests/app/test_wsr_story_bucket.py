from app.constants.ppt_mapping import wsr_story_bucket


def test_only_explicit_done_statuses_are_completed():
    for status in ("Done", "closed", "Resolved", "Completed"):
        assert wsr_story_bucket(status) == "completed"


def test_to_do_is_never_completed():
    for status in ("To Do", "to-do", "TODO", "Open", "Backlog"):
        assert wsr_story_bucket(status) == "inprogress"
        assert wsr_story_bucket(status) != "completed"


def test_in_review_and_in_progress_buckets():
    assert wsr_story_bucket("In Review") == "released"
    assert wsr_story_bucket("In-Progress") == "inprogress"


def test_unknown_status_defaults_to_inprogress_not_completed():
    assert wsr_story_bucket("Some New Jira Status") == "inprogress"
