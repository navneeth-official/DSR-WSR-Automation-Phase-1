"""Generate short WSR slide titles from Jira summary/description via LLM."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.config import llm_configured
from app.constants.ppt_mapping import MAX_TITLE_LENGTH
from app.services.llm_client import complete_text

if TYPE_CHECKING:
    from app.models.jira_story import JiraStory


class TitleGenerationError(Exception):
    """Raised when LLM title generation fails and fallback is disabled."""


SYSTEM_PROMPT = """You write one-line WSR slide bullets for H-E-B delivery status decks.
Output a single short action phrase (Validate, Implement, Add, Fix, Update, …) that tells a non-technical reader what was done.
Rules:
- Max 80 characters
- No Jira keys (e.g. LOC-1234)
- No pipe-separated prefixes like "FAM | MFR |"
- Plain sentence case, no quotes
Examples:
- Implement Warehouse List Page UI
- Validate tax exempt TIN validation on supplier form
- Add validation for warehouse number minimum length
- Fix status column display for offsite warehouses
"""

DESCRIPTION_MAX_CHARS = 500
DEFAULT_SUGGESTION_COUNT = 6

SUGGESTIONS_SYSTEM_PROMPT = """You write one-line WSR slide bullets for H-E-B delivery status decks.
Given a Jira summary and description, output {count} DISTINCT short title options.
Rules for every title:
- Max 80 characters
- Start with an action verb when possible (Validate, Implement, Add, Fix, Update, …)
- No Jira keys (e.g. LOC-1234)
- No pipe-separated prefixes like "FAM | MFR |"
- Plain sentence case, no quotes
Output format: one title per line. No numbering, bullets, or extra commentary.
"""


def _parse_title_lines(text: str, max_count: int) -> list[str]:
    """Parse newline- or bullet-separated title lines from model output."""
    lines: list[str] = []
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*•]\s+", "", line)
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        cleaned = _clean_model_output(line)
        if cleaned and cleaned not in lines:
            lines.append(cleaned)
        if len(lines) >= max_count:
            break
    return lines


def _fallback_title_suggestions(
    *,
    jira_key: str,
    summary: str,
    description: str | None,
    count: int = DEFAULT_SUGGESTION_COUNT,
) -> list[str]:
    """Deterministic title alternatives when the LLM is unavailable."""
    s = (summary or "").strip()
    desc = (description or "").strip()
    stripped = _strip_prefix(s) if s else ""
    desc_first = desc.split(".")[0].strip() if desc else ""

    candidates: list[str] = []

    def add(text: str) -> None:
        cleaned = _clean_model_output(text)
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    add(fallback_title(s, description))
    if stripped and stripped != candidates[0]:
        add(stripped)
    if desc_first and desc_first not in candidates:
        add(desc_first)
    if s and jira_key:
        add(f"{jira_key} — {stripped or s}")
    if desc and desc != s and desc not in candidates:
        snippet = desc if len(desc) <= MAX_TITLE_LENGTH else desc[: MAX_TITLE_LENGTH - 3] + "..."
        add(snippet)
    if s:
        add(f"Delivery update: {stripped or s}")

    idx = 0
    while len(candidates) < count and idx < count * 2:
        base = candidates[0] if candidates else fallback_title(s, description)
        variant = f"{base} (alt {len(candidates)})"
        add(variant)
        idx += 1

    return candidates[:count]


def generate_title_suggestions(
    *,
    jira_key: str,
    summary: str,
    description: str | None,
    count: int = DEFAULT_SUGGESTION_COUNT,
) -> list[str]:
    """Return multiple title options from summary/description (LLM or fallback)."""
    if not _story_has_title_source(summary, description):
        return []

    desc = (description or "")[:DESCRIPTION_MAX_CHARS]
    user_msg = f"jira_key: {jira_key}\nsummary: {summary}\ndescription: {desc}"
    n = max(1, min(count, 10))

    if llm_configured():
        try:
            content = complete_text(
                system_prompt=SUGGESTIONS_SYSTEM_PROMPT.format(count=n),
                user_prompt=user_msg,
                temperature=0.65,
                max_output_tokens=400,
            )
            if content:
                parsed = _parse_title_lines(content, n)
                if parsed:
                    if len(parsed) < n:
                        for alt in _fallback_title_suggestions(
                            jira_key=jira_key,
                            summary=summary,
                            description=description,
                            count=n,
                        ):
                            if alt not in parsed:
                                parsed.append(alt)
                            if len(parsed) >= n:
                                break
                    return parsed[:n]
        except Exception as exc:
            print(f"  Warning: LLM title suggestions failed for {jira_key}: {exc}")

    return _fallback_title_suggestions(
        jira_key=jira_key,
        summary=summary,
        description=description,
        count=n,
    )


def suggest_regenerated_titles(story: JiraStory, *, count: int = DEFAULT_SUGGESTION_COUNT) -> list[str]:
    """Return title suggestions for a story without mutating ``story.title``."""
    return generate_title_suggestions(
        jira_key=story.jira_key,
        summary=story.summary,
        description=story.description,
        count=count,
    )


def _strip_prefix(summary: str) -> str:
    """Remove common Jira pipe-prefix segments for fallback titles."""
    text = summary.strip()
    if "|" in text:
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) > 1:
            text = parts[-1]
    return text


def fallback_title(summary: str, description: str | None = None) -> str:
    """Derive a title without calling the API."""
    base = _strip_prefix(summary)
    if description and (len(base) <= 3 or base.isdigit()):
        first = description.strip().split(".")[0].strip()
        if len(first) > len(base):
            base = first
    base = re.sub(r"\s+", " ", base).strip()
    if len(base) > MAX_TITLE_LENGTH:
        base = base[: MAX_TITLE_LENGTH - 3].rsplit(" ", 1)[0] + "..."
    return base or "Story update"


def _clean_model_output(text: str) -> str:
    cleaned = text.strip().strip("\"'")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > MAX_TITLE_LENGTH:
        cleaned = cleaned[: MAX_TITLE_LENGTH - 3].rsplit(" ", 1)[0] + "..."
    return cleaned


def generate_title(
    *,
    jira_key: str,
    summary: str,
    description: str | None,
    allow_fallback: bool = True,
) -> str:
    """Call the configured LLM for one story title; optional fallback on failure."""
    desc = (description or "")[:DESCRIPTION_MAX_CHARS]
    user_msg = f"jira_key: {jira_key}\nsummary: {summary}\ndescription: {desc}"

    try:
        content = complete_text(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_msg,
            temperature=0.3,
            max_output_tokens=60,
        )
        if content:
            return _clean_model_output(content)
        if not allow_fallback:
            raise TitleGenerationError(
                f"LLM returned empty title for {jira_key}"
            )
    except TitleGenerationError:
        raise
    except Exception as exc:
        if not allow_fallback:
            raise TitleGenerationError(
                f"LLM title failed for {jira_key}: {exc}"
            ) from exc
        print(f"  Warning: LLM title failed for {jira_key}: {exc}")

    return fallback_title(summary, description)


def _story_has_title_source(summary: str, description: str | None) -> bool:
    return bool(summary and summary.strip()) or bool(
        description and description.strip()
    )


def force_regenerate_title(story: JiraStory) -> bool:
    """
    Replace ``story.title`` with a newly generated value from summary/description.

    Returns True when a title was assigned.
    """
    if not _story_has_title_source(story.summary, story.description):
        return False

    if llm_configured():
        story.title = generate_title(
            jira_key=story.jira_key,
            summary=story.summary,
            description=story.description,
            allow_fallback=True,
        )
    else:
        story.title = fallback_title(story.summary, story.description)
    return True


def assign_title_if_missing(story: JiraStory) -> bool:
    """
    Set ``story.title`` from summary/description when empty.

    Uses the LLM when configured, otherwise a deterministic fallback.
    Returns True when a new title was assigned.
    """
    if story.title and story.title.strip():
        return False

    if not _story_has_title_source(story.summary, story.description):
        return False

    if llm_configured():
        story.title = generate_title(
            jira_key=story.jira_key,
            summary=story.summary,
            description=story.description,
            allow_fallback=True,
        )
    else:
        story.title = fallback_title(story.summary, story.description)
    return True


def generate_and_assign_title(story: JiraStory) -> bool:
    """
    Generate and set ``story.title`` via LLM when missing.

    Returns True when a new title was generated, False when an existing title
    was kept or there is no summary/description to generate from.

    Raises TitleGenerationError when LLM credentials are missing or generation fails.
    """
    if story.title and story.title.strip():
        return False

    if not _story_has_title_source(story.summary, story.description):
        return False

    if not llm_configured():
        raise TitleGenerationError(
            "LLM credentials required for title generation. "
            "Set GEMINI_API_KEY, or AZURE_OPENAI_*, or OPENAI_API_KEY in .env"
        )

    story.title = generate_title(
        jira_key=story.jira_key,
        summary=story.summary,
        description=story.description,
        allow_fallback=False,
    )
    return True


def ensure_story_titles(
    stories: list[JiraStory],
    *,
    save: bool = False,
    db: Session | None = None,
    rate_limit_s: float = 0.2,
    regenerate: bool = False,
) -> tuple[int, int]:
    """
    Fill missing title on each story (in memory and optionally DB).
    Returns (generated_count, reused_count).
    """
    if not llm_configured():
        print(
            "Warning: No LLM credentials — set GEMINI_API_KEY, AZURE_OPENAI_*, "
            "or OPENAI_API_KEY in .env; using fallback titles only."
        )

    generated = 0
    reused = 0

    for story in stories:
        if story.title and story.title.strip() and not regenerate:
            reused += 1
            continue

        if llm_configured():
            story.title = generate_title(
                jira_key=story.jira_key,
                summary=story.summary,
                description=story.description,
            )
            generated += 1
            time.sleep(rate_limit_s)
        else:
            story.title = fallback_title(story.summary, story.description)
            generated += 1

        # Title is set on the in-session story instance; caller commits when save=True.

    return generated, reused
