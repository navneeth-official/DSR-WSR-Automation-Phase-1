"""AI summarization for monthly Accomplishments slides (pluggable backend)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from monthly_report.stories import StoryRecord

_JIRA_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


@dataclass(frozen=True)
class AccomplishmentsSummary:
    """Validated bullet lists for one project Accomplishments slide."""

    completed: tuple[str, ...]
    in_progress: tuple[str, ...]

    def slide_lines(self, *, max_lines: int) -> list[str]:
        """Completed items first, then ongoing work — same sentence style (no status prefix)."""
        lines: list[str] = []
        for bullet in self.completed:
            if len(lines) >= max_lines:
                break
            lines.append(bullet)
        for bullet in self.in_progress:
            if len(lines) >= max_lines:
                break
            lines.append(bullet)
        return lines


@dataclass(frozen=True)
class SummarizerConfig:
    max_stories: int = 120
    max_bullets_completed: int = 6
    max_bullets_in_progress: int = 4
    max_chars_per_bullet: int = 220
    max_slide_lines: int = 6
    temperature: float = 0.35


class AccomplishmentsSummarizerError(Exception):
    """Summarization failed or the model returned unusable output."""


@runtime_checkable
class AccomplishmentsSummarizer(Protocol):
    def summarize(
        self,
        *,
        project_name: str,
        period_label: str,
        stories: list[StoryRecord],
    ) -> AccomplishmentsSummary: ...


SYSTEM_PROMPT = """You write Accomplishments bullets for an H-E-B Supplier/Pricing cadence PowerPoint slide.
Match the tone and structure of these REAL examples from leadership decks:

Completed style:
- Implemented IRS success event and Datadog dashboard for status
- Implemented GIIN validation endpoint
- Removed Wentworth registration update and dump topics and message flows
- Fixed GCP bucket name mismatch in prod API configurations
- Supplier Registration Invite email content is updated according to the requested verbiage changes
- Resolved failed test scripts in scheduling notifications and topics page

Ongoing / in-sprint style (still full sentences, no labels):
- Initiated automation of the Partner SIDM application
- Identified the application scenarios and functionalities suitable for automation

Return ONLY valid JSON:
{"completed": ["..."], "in_progress": ["..."]}

Rules:
- Each string is ONE accomplishment bullet (no leading "•", "-", or numbering).
- Start with a strong verb: Implemented, Fixed, Removed, Updated, Resolved, Added, Completed, Initiated, Identified, Validated, etc.
- Prefer past tense for finished work; present or past for work still in flight — never prefix "(In progress)".
- Write full stakeholder-friendly sentences (what changed and why it matters), not WSR-style 5-word fragments.
- No Jira keys. No pipe-separated ticket prefixes.
- Max 220 characters per bullet. Up to 6 completed and 4 in_progress items; omit noise.
- Consolidate related stories into one bullet when they tell one outcome.
"""


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def summarizer_config_from_env() -> SummarizerConfig:
    return SummarizerConfig(
        max_stories=_env_int("MSR_ACCOMPLISHMENTS_MAX_STORIES", 120),
        max_bullets_completed=_env_int("MSR_ACCOMPLISHMENTS_MAX_COMPLETED", 4),
        max_bullets_in_progress=_env_int("MSR_ACCOMPLISHMENTS_MAX_IN_PROGRESS", 3),
        max_chars_per_bullet=_env_int("MSR_ACCOMPLISHMENTS_MAX_CHARS", 140),
        max_slide_lines=_env_int("MSR_ACCOMPLISHMENTS_SLIDE_LINES", 6),
    )


def accomplishments_enabled() -> bool:
    flag = os.environ.get("MSR_ACCOMPLISHMENTS", "auto").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    # auto: only when LLM credentials exist
    try:
        from app.config import llm_configured

        return llm_configured()
    except ImportError:
        return False


def accomplishments_model_override() -> str | None:
    """
    Optional deployment override (``MSR_ACCOMPLISHMENTS_MODEL``).

    When unset, accomplishments use the same client and deployment as WSR story
    title generation (``create_llm_client`` → ``AZURE_OPENAI_MODEL`` / OpenAI default).
    """
    override = os.environ.get("MSR_ACCOMPLISHMENTS_MODEL", "").strip()
    return override or None


def _story_display_title(story: StoryRecord) -> str:
    if story.title and story.title.strip():
        return story.title.strip()
    return story.summary.strip()


def _prepare_story_payload(stories: list[StoryRecord], config: SummarizerConfig) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for story in stories[: config.max_stories]:
        desc = (story.description or "").strip()
        if len(desc) > 400:
            desc = desc[:397] + "..."
        payload.append(
            {
                "summary": story.summary.strip(),
                "title": _story_display_title(story),
                "status": story.status,
                "bucket": story.category,
                "sprint": story.sprint_name or "",
                "description": desc,
            }
        )
    return payload


def _clean_bullet(text: str, max_chars: int) -> str:
    cleaned = re.sub(r"^\(in progress\)\s*", "", (text or ""), flags=re.I)
    cleaned = _JIRA_KEY_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip("-•")
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 3].rsplit(" ", 1)[0] + "..."
    return cleaned


def validate_summary(
    raw: dict,
    *,
    config: SummarizerConfig,
) -> AccomplishmentsSummary:
    if not isinstance(raw, dict):
        raise AccomplishmentsSummarizerError("Model output is not a JSON object")

    completed_raw = raw.get("completed") or []
    in_progress_raw = raw.get("in_progress") or []
    if not isinstance(completed_raw, list) or not isinstance(in_progress_raw, list):
        raise AccomplishmentsSummarizerError("completed and in_progress must be arrays")

    completed: list[str] = []
    for item in completed_raw:
        if not isinstance(item, str):
            continue
        bullet = _clean_bullet(item, config.max_chars_per_bullet)
        if bullet:
            completed.append(bullet)
        if len(completed) >= config.max_bullets_completed:
            break

    in_progress: list[str] = []
    for item in in_progress_raw:
        if not isinstance(item, str):
            continue
        bullet = _clean_bullet(item, config.max_chars_per_bullet)
        if bullet:
            in_progress.append(bullet)
        if len(in_progress) >= config.max_bullets_in_progress:
            break

    if not completed and not in_progress:
        raise AccomplishmentsSummarizerError("Model returned no usable bullets")

    return AccomplishmentsSummary(
        completed=tuple(completed),
        in_progress=tuple(in_progress),
    )


class OpenAIAccomplishmentsSummarizer:
    """Uses the same Azure/OpenAI client factory as weekly WSR title generation."""

    def __init__(
        self,
        *,
        config: SummarizerConfig | None = None,
        client_factory=None,
        model: str | None = None,
    ) -> None:
        self.config = config or summarizer_config_from_env()
        self._client_factory = client_factory
        self._model_override = model or accomplishments_model_override()

    def summarize(
        self,
        *,
        project_name: str,
        period_label: str,
        stories: list[StoryRecord],
    ) -> AccomplishmentsSummary:
        if not stories:
            raise AccomplishmentsSummarizerError(f"No stories to summarize for {project_name!r}")

        if self._client_factory is None:
            from app.services.title_generator import create_llm_client

            self._client_factory = create_llm_client

        client, title_model = self._client_factory()
        if client is None or not title_model:
            raise AccomplishmentsSummarizerError(
                "LLM not configured. Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY "
                "and AZURE_OPENAI_MODEL (same as story title generation), or OPENAI_API_KEY."
            )

        model = self._model_override or title_model
        payload = _prepare_story_payload(stories, self.config)
        user_msg = json.dumps(
            {
                "project": project_name,
                "report_period": period_label,
                "stories": payload,
            },
            ensure_ascii=False,
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=500,
                temperature=self.config.temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise AccomplishmentsSummarizerError(f"LLM request failed: {exc}") from exc

        content = response.choices[0].message.content
        if not content:
            raise AccomplishmentsSummarizerError("Empty model response")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AccomplishmentsSummarizerError(f"Model did not return JSON: {exc}") from exc

        return validate_summary(parsed, config=self.config)


def resolve_summarizer() -> OpenAIAccomplishmentsSummarizer | None:
    if not accomplishments_enabled():
        return None
    return OpenAIAccomplishmentsSummarizer()
