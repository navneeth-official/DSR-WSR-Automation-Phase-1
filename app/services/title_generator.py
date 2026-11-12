"""Generate short WSR slide titles from Jira summary/description via GPT-4o mini."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.config import llm_configured
from app.constants.ppt_mapping import MAX_TITLE_LENGTH
from app.services.llm_client import create_llm_client, llm_credentials_help

# Re-export for call sites that import create_llm_client from this module.
__all__ = (
    "TitleGenerationError",
    "create_llm_client",
    "ensure_story_titles",
    "fallback_title",
    "generate_and_assign_title",
    "generate_title",
)

if TYPE_CHECKING:
    from app.models.jira_story import JiraStory


class TitleGenerationError(Exception):
    """Raised when GPT title generation fails and fallback is disabled."""


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
    client,
    *,
    jira_key: str,
    summary: str,
    description: str | None,
    model: str,
    allow_fallback: bool = True,
) -> str:
    """Call the configured LLM for one story title; optional fallback on failure."""
    desc = (description or "")[:DESCRIPTION_MAX_CHARS]
    user_msg = f"jira_key: {jira_key}\nsummary: {summary}\ndescription: {desc}"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=60,
            temperature=0.3,
        )
        content = response.choices[0].message.content
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


def generate_and_assign_title(story: JiraStory) -> bool:
    """
    Generate and set ``story.title`` via GPT when missing.

    Returns True when a new title was generated, False when an existing title
    was kept or there is no summary/description to generate from.

    Raises TitleGenerationError when LLM credentials are missing or the call fails.
    """
    if story.title and story.title.strip():
        return False

    if not _story_has_title_source(story.summary, story.description):
        return False

    if not llm_configured():
        raise TitleGenerationError(
            "LLM credentials required for title generation. " + llm_credentials_help()
        )

    client, model = create_llm_client()
    if not client or not model:
        raise TitleGenerationError("Failed to create LLM client")

    story.title = generate_title(
        client,
        jira_key=story.jira_key,
        summary=story.summary,
        description=story.description,
        model=model,
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
            "Warning: No LLM credentials — "
            f"{llm_credentials_help()} Using fallback titles only."
        )

    client, model = create_llm_client()
    generated = 0
    reused = 0

    for story in stories:
        if story.title and story.title.strip() and not regenerate:
            reused += 1
            continue

        if client and model:
            story.title = generate_title(
                client,
                jira_key=story.jira_key,
                summary=story.summary,
                description=story.description,
                model=model,
            )
            generated += 1
            time.sleep(rate_limit_s)
        else:
            story.title = fallback_title(story.summary, story.description)
            generated += 1

        if save and db is not None:
            row = db.get(type(story), story.jira_key)
            if row:
                row.title = story.title

    return generated, reused
