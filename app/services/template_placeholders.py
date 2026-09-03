"""Placeholder registry and context for template-driven content insertion."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

_PLACEHOLDER_TOKEN_RE = re.compile(r"\{([^}]+)\}")

# Normalized token name -> canonical key
_TOKEN_ALIASES: dict[str, str] = {
    "track name": "track_name",
    "service name": "track_name",
    "sprint name": "sprint_name",
    "status": "status",
    "from date": "from_date",
    "to date": "to_date",
    "dates": "dates",
    "count": "count",
    "total": "total",
    "done": "done",
    "completed": "done",
    "in-review": "in_review",
    "in review": "in_review",
    "in-progress": "in_progress",
    "in progress": "in_progress",
    # Authoring token on story bullet prototype — filled via set_story_line_text, not substitution.
    "story title": "story_title",
    "story name": "story_title",
  # Bucket-specific story bullets — bucket inferred from token, not paragraph order.
    "completed story title": "completed_story_title",
    "completed story name": "completed_story_title",
    "in-review story title": "in_review_story_title",
    "in review story title": "in_review_story_title",
    "released story title": "released_story_title",
    "released story name": "released_story_title",
    "in-progress story title": "in_progress_story_title",
    "in progress story title": "in_progress_story_title",
    # Bucket-specific category counts — bucket inferred from token, not paragraph order.
    "completed count": "completed_count",
    "in-review count": "in_review_count",
    "in review count": "in_review_count",
    "released count": "released_count",
    "in-progress count": "in_progress_count",
    "in progress count": "in_progress_count",
    "week start date": "week_start_date",
    "week end date": "week_end_date",
}

# Canonical token key -> story bucket (completed / released / inprogress).
BUCKET_STORY_TITLE_KEYS: dict[str, str] = {
    "completed_story_title": "completed",
    "in_review_story_title": "released",
    "released_story_title": "released",
    "in_progress_story_title": "inprogress",
}

BUCKET_COUNT_KEYS: dict[str, str] = {
    "completed_count": "completed",
    "in_review_count": "released",
    "released_count": "released",
    "in_progress_count": "inprogress",
}

STORY_TITLE_TOKEN_KEYS: frozenset[str] = frozenset(
    {"story_title", *BUCKET_STORY_TITLE_KEYS.keys()}
)


def normalize_token_name(raw: str) -> str:
    key = re.sub(r"\s+", " ", (raw or "").strip().lower())
    return _TOKEN_ALIASES.get(key, key.replace(" ", "_"))


def bucket_from_token_keys(keys: set[str]) -> str | None:
    """Map normalized placeholder keys to a story bucket when tokens are bucket-specific."""
    for key in keys:
        bucket = BUCKET_STORY_TITLE_KEYS.get(key)
        if bucket is not None:
            return bucket
        bucket = BUCKET_COUNT_KEYS.get(key)
        if bucket is not None:
            return bucket
    return None


def find_placeholder_tokens(text: str) -> list[str]:
    """Return raw placeholder names as they appear inside braces."""
    return [m.group(1).strip() for m in _PLACEHOLDER_TOKEN_RE.finditer(text or "")]


def paragraph_has_placeholders(text: str) -> bool:
    return bool(_PLACEHOLDER_TOKEN_RE.search(text or ""))


@dataclass
class PlaceholderContext:
    """Values available for template placeholder substitution."""

    track_name: str = ""
    sprint_name: str = ""
    status: str = ""
    from_date: str = ""
    to_date: str = ""
    dates: str = ""
    total: str = "0"
    done: str = "0"
    in_review: str = "0"
    in_progress: str = "0"
    count: str = "0"
    week_start_date: str = ""
    week_end_date: str = ""
    extra: dict[str, str] = field(default_factory=dict)
    _unknown_logged: set[str] = field(default_factory=set, repr=False)

    @classmethod
    def from_section(
        cls,
        section: Any,
        *,
        track_name: str = "",
        bucket: str | None = None,
    ) -> PlaceholderContext:
        """Build context from SprintSection or dict-like section payload."""
        if hasattr(section, "sprint_name"):
            sprint_name = section.sprint_name
            status = section.sprint_status
            dates = section.sprint_dates
            completed = list(section.completed)
            released = list(section.released)
            inprogress = list(section.inprogress)
            start = getattr(section, "sprint_start_date", None)
            end = getattr(section, "sprint_end_date", None)
        else:
            data = section if isinstance(section, dict) else {}
            sprint_name = str(data.get("sprint_name") or "")
            status = str(data.get("sprint_status") or "In-progress")
            dates = str(data.get("sprint_dates") or "")
            completed = list(data.get("completed") or data.get("completed_items") or [])
            released = list(data.get("released") or data.get("released_items") or [])
            inprogress = list(data.get("inprogress") or data.get("inprogress_items") or [])
            start = data.get("sprint_start_date")
            end = data.get("sprint_end_date")

        from_date = _format_date(start)
        to_date = _format_date(end)
        if not dates and from_date and to_date:
            dates = f"{from_date} – {to_date}"

        total_n = len(completed) + len(released) + len(inprogress)
        count = str(
            {
                "completed": len(completed),
                "released": len(released),
                "inprogress": len(inprogress),
            }.get(bucket or "", total_n)
        )

        return cls(
            track_name=track_name,
            sprint_name=sprint_name,
            status=status,
            from_date=from_date,
            to_date=to_date,
            dates=dates,
            total=str(total_n),
            done=str(len(completed)),
            in_review=str(len(released)),
            in_progress=str(len(inprogress)),
            count=count,
        )

    @classmethod
    def from_report_period(
        cls,
        report_start_date: Any,
        report_end_date: Any,
        **kwargs: Any,
    ) -> PlaceholderContext:
        """Build context for deck-level week range placeholders."""
        return cls(
            week_start_date=_format_date(report_start_date),
            week_end_date=_format_date(report_end_date),
            **kwargs,
        )

    def resolve(self, token_raw: str) -> str | None:
        key = normalize_token_name(token_raw)
        mapping = {
            "track_name": self.track_name,
            "sprint_name": self.sprint_name,
            "status": self.status,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "dates": self.dates,
            "total": self.total,
            "done": self.done,
            "in_review": self.in_review,
            "in_progress": self.in_progress,
            "count": self.count,
            "week_start_date": self.week_start_date,
            "week_end_date": self.week_end_date,
        }
        if key in mapping:
            return mapping[key]
        if key in BUCKET_COUNT_KEYS:
            return {
                "completed": self.done,
                "released": self.in_review,
                "inprogress": self.in_progress,
            }[BUCKET_COUNT_KEYS[key]]
        if key in STORY_TITLE_TOKEN_KEYS:
            return self.extra.get("story_title", "")
        if key in self.extra:
            return self.extra[key]
        if token_raw not in self._unknown_logged:
            logger.warning("Unknown template placeholder: {%s}", token_raw)
            self._unknown_logged.add(token_raw)
        return None


def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    text = str(value).strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10]).strftime("%d %b %Y")
    except ValueError:
        return text
