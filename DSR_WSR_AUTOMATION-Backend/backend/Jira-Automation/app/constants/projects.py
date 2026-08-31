"""Canonical HEB project names and short keys for the projects lookup table."""

# project_name (from Rovo) -> project_key (stored in DB)
CANONICAL_PROJECT_KEYS: dict[str, str] = {
    "LOCO": "LOC",
    "Cost Core Service": "COST",
    "GSS": "GSS",
    "Wentforth": "WNF",
    "Pharamacy": "PHRM",
    "Supplier QA": "SUP",
    "SPUR": "SPUR",
    "Pricing": "PRC",
}

CANONICAL_PROJECT_NAMES: tuple[str, ...] = tuple(CANONICAL_PROJECT_KEYS.keys())
