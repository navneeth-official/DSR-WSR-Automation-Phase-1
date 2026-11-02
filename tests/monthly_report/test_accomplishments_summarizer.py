from monthly_report.accomplishments_summarizer import (
    AccomplishmentsSummary,
    AccomplishmentsSummarizerError,
    OpenAIAccomplishmentsSummarizer,
    validate_summary,
)
from monthly_report.accomplishments_summarizer import SummarizerConfig
from monthly_report.stories import StoryRecord


def test_validate_summary_splits_and_cleans():
    raw = {
        "completed": ["Shipped pricing API", "PRC-99 cleanup"],
        "in_progress": ["Rollout to stores"],
    }
    summary = validate_summary(raw, config=SummarizerConfig())
    assert summary.completed[0] == "Shipped pricing API"
    assert "PRC" not in summary.completed[1]
    assert summary.in_progress == ("Rollout to stores",)


def test_slide_lines_prioritize_completed_then_in_progress():
    summary = AccomplishmentsSummary(
        completed=("A", "B"),
        in_progress=("C",),
    )
    lines = summary.slide_lines(max_lines=3)
    assert lines == ["A", "B", "C"]


def test_summarizer_uses_title_generation_deployment(monkeypatch):
    captured: dict[str, str] = {}

    class _FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(*, model, **kwargs):
                    captured["model"] = model
                    class _Msg:
                        content = '{"completed": ["Done"], "in_progress": []}'

                    class _Choice:
                        message = _Msg()

                    class _Resp:
                        choices = [_Choice()]

                    return _Resp()

    def _factory():
        return _FakeClient(), "my-title-deployment"

    summarizer = OpenAIAccomplishmentsSummarizer(client_factory=_factory)
    story = StoryRecord(
        jira_key="X-1",
        summary="S",
        title=None,
        description=None,
        status="Done",
        sprint_name="Sp",
        story_points=None,
        category="completed",
    )
    summarizer.summarize(project_name="P", period_label="2026-06", stories=[story])
    assert captured["model"] == "my-title-deployment"


def test_validate_summary_rejects_empty():
    try:
        validate_summary({"completed": [], "in_progress": []}, config=SummarizerConfig())
        assert False, "expected error"
    except AccomplishmentsSummarizerError:
        pass
