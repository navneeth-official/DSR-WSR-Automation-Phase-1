"""Discover index-table slot positions from any WSR template."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from app.services.ppt_shape_utils import normalize_title_text

INDEX_ENTRY_RULES: tuple[tuple[tuple[str, ...], str, bool], ...] = (
    (("cost core",), "Cost Core Service", True),
    (("supplier core",), "Supplier Core Service", True),
    (("pricing core",), "Pricing Core Service", True),
    (("wentworth",), "Wentworth", True),
    (("location core",), "Location Core Service", True),
    (("pharmacy",), "Pharmacy and Wellness", True),
    (("global sourcing",), "Global Sourcing Solution", True),
    (("product attribute",), "Product Attribute Management", True),
    (("loco",), "LoCo", True),
    (("bsa",), "LoCo", True),
    (("matters of attention",), "Matters of Attention", False),
    (("team allocation",), "Team Allocation", False),
)


def _normalize_index_text(text: str) -> str:
    return normalize_title_text(text).lower()


def _cell_identity(cell) -> int:
    return id(cell._tc)


@dataclass(frozen=True)
class IndexSlot:
    row: int
    col: int
    needles: tuple[str, ...]
    search_title: str
    is_delivery: bool


@dataclass
class IndexLayout:
    slots: list[IndexSlot] = field(default_factory=list)
    column_prototypes: dict[int, Any] = field(default_factory=dict)

    def slot_for(self, search_title: str) -> IndexSlot | None:
        needle = search_title.lower()
        for slot in self.slots:
            if slot.search_title.lower() == needle:
                return slot
        return None

    def delivery_slots(self) -> list[IndexSlot]:
        return [slot for slot in self.slots if slot.is_delivery]

    def static_slots(self) -> list[IndexSlot]:
        return [slot for slot in self.slots if not slot.is_delivery]

    def grid_positions(self, rows: int, cols: int) -> list[tuple[int, int]]:
        return [(row, col) for row in range(rows) for col in range(cols)]


def capture_column_prototypes(table, layout: IndexLayout) -> dict[int, Any]:
    """Snapshot top cell body per column so reflow keeps alignment."""
    prototypes: dict[int, Any] = {}
    for slot in sorted(layout.slots, key=lambda s: (s.row, s.col)):
        if slot.col in prototypes:
            continue
        cell = table.cell(slot.row, slot.col)
        prototypes[slot.col] = copy.deepcopy(cell.text_frame._txBody)
    return prototypes


def discover_index_layout(table) -> IndexLayout:
    """Map INDEX_ENTRY_RULES to (row, col) by reading template cell labels."""
    layout = IndexLayout()
    used_positions: set[tuple[int, int]] = set()
    assigned_titles: set[str] = set()

    for needles, search_title, is_delivery in INDEX_ENTRY_RULES:
        title_key = search_title.lower()
        if title_key in assigned_titles:
            continue
        for row_idx, row in enumerate(table.rows):
            for col_idx in range(len(table.columns)):
                pos = (row_idx, col_idx)
                if pos in used_positions:
                    continue
                cell = table.cell(row_idx, col_idx)
                text = _normalize_index_text(cell.text_frame.text)
                if not text or not all(needle in text for needle in needles):
                    continue
                layout.slots.append(
                    IndexSlot(
                        row=row_idx,
                        col=col_idx,
                        needles=needles,
                        search_title=search_title,
                        is_delivery=is_delivery,
                    )
                )
                used_positions.add(pos)
                assigned_titles.add(title_key)
                break
            else:
                continue
            break

    layout.column_prototypes = capture_column_prototypes(table, layout)
    return layout
