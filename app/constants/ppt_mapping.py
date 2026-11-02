"""PPT delivery-status deck mappings and status bucketing rules."""

from __future__ import annotations

import re

# project_key -> slide title in HEB WSR deck (Delivery status – …)
PPT_SLIDE_TITLES: dict[str, str] = {
    "COST": "Cost Core Service",
    "SUP": "Supplier Core Service",  # G10X layout alias in update_delivery_status.G10X_LAYOUT_BY_TITLE
    "SPUR": "Supplier Core Service",
    "PRC": "Pricing Core Service",
    "WNF": "Wentworth",
    "LOC": "Location Core Service",
    "PHRM": "Pharmacy and Wellness",
    "GSS": "Global Sourcing Solution",
}

# Deck slide order (matches G10X template)
PPT_SLIDE_ORDER: list[str] = [
    "COST",
    "SUP",
    "SPUR",
    "PRC",
    "WNF",
    "LOC",
    "PHRM",
    "GSS",
]

# Jira status (normalized lowercase) -> highlights bucket
STATUS_TO_BUCKET: dict[str, str] = {
    "done": "completed",
    "closed": "completed",
    "resolved": "completed",
    "completed": "completed",
    "in review": "released",
    "in-review": "released",
    "ready for qa": "released",
    "in progress": "inprogress",
    "in-progress": "inprogress",
    "in development": "inprogress",
    "to do": "inprogress",
    "open": "inprogress",
    "backlog": "inprogress",
}

# Unknown statuses must never land in completed (only explicit keys above).
WSR_UNKNOWN_STATUS_BUCKET = "inprogress"


def normalize_jira_status(status: str | None) -> str:
    return re.sub(r"[\s_-]+", " ", (status or "").strip().lower())


def wsr_story_bucket(status: str | None) -> str:
    """Map ``jira_stories.status`` to completed / released / inprogress."""
    return STATUS_TO_BUCKET.get(normalize_jira_status(status), WSR_UNKNOWN_STATUS_BUCKET)

# Blank KA bullet rows reserved for manual BSA entry
KA_PLACEHOLDER_ROWS = 4

MAX_TITLE_LENGTH = 80
