"""Placeholder names and the values that replace them."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime


_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
_COUNT_LABEL_RE = re.compile(
    r"(in[\s\-]*progress|in[\s\-]*review|completed|total)\s*[–\-:]?\s*$",
    re.IGNORECASE,
)


def normalize_token_name(raw: str) -> str:
    text = re.sub(r"[\s_\-]+", " ", (raw or "").strip().lower())
    return text.replace(" ", "_")


def find_placeholder_tokens(text: str) -> list[str]:
    return [match.group(1).strip() for match in _TOKEN_RE.finditer(text or "")]


def _items(section: dict, *keys: str) -> list[str]:
    for key in keys:
        value = section.get(key)
        if value:
            return [str(item) for item in value]
    return []


def _display_date(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%b %d"):
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d":
            return f"{parsed.day} {parsed.strftime('%b %Y')}"
        return raw
    return raw


@dataclass
class PlaceholderContext:
    sprint_name: str = ""
    status: str = ""
    from_date: str = ""
    to_date: str = ""
    week_start_date: str = ""
    week_end_date: str = ""
    count: str = ""
    total: str = ""
    completed_count: str = ""
    in_review_count: str = ""
    in_progress_count: str = ""
    track_name: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_report_period(cls, start: str, end: str) -> PlaceholderContext:
        def show(raw: str) -> str:
            parsed = date.fromisoformat(raw)
            return f"{parsed.day} {parsed.strftime('%b %Y')}"

        return cls(week_start_date=show(start), week_end_date=show(end))

    @classmethod
    def from_section(
        cls,
        section: dict,
        bucket: str | None = None,
        track_name: str = "",
    ) -> PlaceholderContext:
        completed = _items(section, "completed", "completed_items")
        released = _items(section, "released", "released_items")
        inprogress = _items(section, "inprogress", "inprogress_items")
        counts = {
            "completed": len(completed),
            "released": len(released),
            "inprogress": len(inprogress),
        }
        dates = str(section.get("sprint_dates") or "")
        from_date = str(section.get("from_date") or "")
        to_date = str(section.get("to_date") or "")
        if dates and not (from_date and to_date):
            parts = re.split(r"\s+[–-]\s+", dates, maxsplit=1)
            if len(parts) == 2:
                from_date, to_date = parts
        return cls(
            sprint_name=str(section.get("sprint_name") or ""),
            status=str(section.get("sprint_status") or section.get("status") or ""),
            from_date=_display_date(from_date) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", from_date) else from_date,
            to_date=_display_date(to_date) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", to_date) else to_date,
            count=str(counts.get(bucket, sum(counts.values()))),
            total=str(sum(counts.values())),
            completed_count=str(counts["completed"]),
            in_review_count=str(counts["released"]),
            in_progress_count=str(counts["inprogress"]),
            track_name=track_name,
        )

    def resolve(self, token: str, *, preceding: str = "") -> str | None:
        key = normalize_token_name(token)
        if key == "count" and preceding:
            labeled = self._count_from_label(preceding)
            if labeled is not None:
                return labeled
        story = self.extra.get("story_title")
        if key in {
            "story_title",
            "completed_story_title",
            "in_review_story_title",
            "in_progress_story_title",
        } and story is not None:
            return story
        values = {
            "sprint_name": self.sprint_name,
            "status": self.status,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "week_start_date": self.week_start_date,
            "week_end_date": self.week_end_date,
            "count": self.count,
            "total": self.total,
            "completed_count": self.completed_count,
            "in_review_count": self.in_review_count,
            "in_progress_count": self.in_progress_count,
            "track_name": self.track_name,
        }
        if key not in values:
            return None
        return values[key]

    def _count_from_label(self, preceding: str) -> str | None:
        """Map a repeated {Count} to the label sitting directly in front of it."""
        match = _COUNT_LABEL_RE.search(preceding[-80:])
        if match is None:
            return None
        label = re.sub(r"[\s_\-]+", "", match.group(1).lower())
        if label == "total":
            return self.total
        if label == "completed":
            return self.completed_count
        if "review" in label:
            return self.in_review_count
        if "progress" in label:
            return self.in_progress_count
        return None
