"""Replace template '{ Week End Date }' text with the WSR week being generated."""

from __future__ import annotations

import re
from datetime import date

from pptx.oxml.ns import qn

from app.services.ppt_shape_utils import iter_all_shapes

_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

# Braced form first so "{ Week End Date }" is replaced as one token, braces included.
_WEEK_END_DATE_TOKEN = re.compile(
    r"\{\s*week\s+end\s+date\s*\}|week\s+end\s+date",
    re.IGNORECASE,
)


def format_week_end_date(value: date) -> str:
    """Display form used in highlights headers, e.g. '6 Nov 2026'."""
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def _text_nodes(p_elem):
    return [node for node in p_elem.iter() if node.tag == qn("a:t")]


def _replace_in_paragraph(p_elem, replacement: str) -> bool:
    nodes = _text_nodes(p_elem)
    if not nodes:
        return False

    pieces = [node.text or "" for node in nodes]
    full = "".join(pieces)
    matches = list(_WEEK_END_DATE_TOKEN.finditer(full))
    if not matches:
        return False

    offsets: list[tuple[int, int]] = []
    pos = 0
    for piece in pieces:
        offsets.append((pos, pos + len(piece)))
        pos += len(piece)

    def overlapping(start: int, end: int) -> list[int]:
        return [i for i, (a, b) in enumerate(offsets) if a < end and b > start]

    if all(len(overlapping(match.start(), match.end())) == 1 for match in matches):
        for node, piece in zip(nodes, pieces):
            updated = _WEEK_END_DATE_TOKEN.sub(replacement, piece)
            if updated != piece:
                node.text = updated
        return True

    nodes[0].text = _WEEK_END_DATE_TOKEN.sub(replacement, full)
    for node in nodes[1:]:
        node.text = ""
    return True


def _tx_bodies(shape):
    if getattr(shape, "has_text_frame", False):
        yield shape.text_frame._txBody
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                yield cell.text_frame._txBody


def replace_week_end_date_placeholders(prs, week_end: date) -> int:
    """Replace week-end placeholders on every slide. Returns paragraphs updated."""
    shown = format_week_end_date(week_end)
    updated = 0
    for slide in prs.slides:
        for shape in iter_all_shapes(slide.shapes):
            for body in _tx_bodies(shape):
                for paragraph in body.findall(qn("a:p")):
                    if _replace_in_paragraph(paragraph, shown):
                        updated += 1
    return updated
