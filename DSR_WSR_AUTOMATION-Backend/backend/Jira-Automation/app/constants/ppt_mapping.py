"""PPT delivery-status deck mappings and status bucketing rules."""

# project_key -> slide title in HEB WSR deck (Delivery status – …)
PPT_SLIDE_TITLES: dict[str, str] = {
    "COST": "Cost Core Service",
    "SUP": "Supplier Core Service",  # G10X layout alias in update_delivery_status.G10X_LAYOUT_BY_TITLE
    "SPUR": "Supplier Core Service",
    "PRC": "Pricing Core Service",
    "PRICE": "Pricing Core Service",
    "WNF": "Wentworth",
    "LOC": "Location Core Service",
    "PHRM": "Pharmacy and Wellness",
    "GSS": "Global Sourcing Solution",
    "PATRV": "Patronage Travel",
}

# Deck slide order (matches G10X template); unknown keys sort after these.
PPT_SLIDE_ORDER: list[str] = [
    "COST",
    "SUP",
    "SPUR",
    "PRC",
    "PRICE",
    "WNF",
    "LOC",
    "PHRM",
    "GSS",
    "PATRV",
]

# Jira status (lowercase) -> highlights bucket
STATUS_TO_BUCKET: dict[str, str] = {
    "done": "completed",
    "closed": "completed",
    "resolved": "completed",
    "in review": "released",
    "in-review": "released",
    "ready for qa": "released",
    "in progress": "inprogress",
    "in-progress": "inprogress",
    "in development": "inprogress",
}

# Blank KA bullet rows reserved for manual BSA entry
KA_PLACEHOLDER_ROWS = 4

MAX_TITLE_LENGTH = 80
