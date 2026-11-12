"""``{{Token}}`` replacement that keeps the template's run formatting.

A placeholder may carry an optional display format after ``|``, e.g.
``{{Start date | DD MMM YYYY}}``. The key (``start_date``) selects the value; the
format only changes how dates are written. Font, size and colour always come from
the run that holds the placeholder.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

TOKEN_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_NUMBERED_TOKEN_RE = re.compile(r"^(sprint name|sprint)\s*\d+$")

MONTH_ABBREVIATIONS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sept", "Oct", "Nov", "Dec",
)
_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_DATE_PART_RE = re.compile(r"YYYY|YY|MMMM|MMM|MM|M|DD|D")


@dataclass(frozen=True)
class DateValue:
    """A date written with the placeholder's format, else ``default_format``."""

    value: date
    default_format: str

    def render(self, fmt: str | None) -> str:
        return format_date(self.value, fmt or self.default_format)


TokenValue = str | DateValue


def format_date(value: date, pattern: str) -> str:
    """Render ``value`` with ``YYYY YY MMMM MMM MM M DD D`` parts; other characters stay."""

    def part(match: re.Match[str]) -> str:
        code = match.group(0)
        return {
            "YYYY": f"{value.year:04d}",
            "YY": f"{value.year % 100:02d}",
            "MMMM": _MONTH_NAMES[value.month - 1],
            "MMM": MONTH_ABBREVIATIONS[value.month - 1],
            "MM": f"{value.month:02d}",
            "M": str(value.month),
            "DD": f"{value.day:02d}",
            "D": str(value.day),
        }[code]

    return _DATE_PART_RE.sub(part, pattern)


def split_token(raw: str) -> tuple[str, str | None]:
    """``Start date | DD MMM`` -> (``start_date``, ``DD MMM``)."""
    name, _, fmt = raw.partition("|")
    fmt = fmt.strip() or None
    key = re.sub(r"\s+", " ", name.strip().lower())
    numbered = _NUMBERED_TOKEN_RE.match(key)
    if numbered:
        key = numbered.group(1)
    return key.replace(" ", "_"), fmt


def token_key(raw: str) -> str:
    """``Sprint Name 1`` -> ``sprint_name``, ``Start date`` -> ``start_date``, ``TC`` -> ``tc``."""
    return split_token(raw)[0]


def render_value(value: TokenValue, fmt: str | None) -> str:
    if isinstance(value, DateValue):
        return value.render(fmt)
    return str(value)


def _run_text(run) -> str:
    t = run.find(qn("a:t"))
    return (t.text or "") if t is not None else ""


def _set_run_text(run, value: str) -> None:
    t = run.find(qn("a:t"))
    if t is None:
        t = etree.SubElement(run, qn("a:t"))
    t.text = value


def replace_tokens_in_paragraph(p_elem, values: Mapping[str, TokenValue]) -> list[str]:
    """
    Replace resolvable tokens in an ``a:p`` element; return tokens left unresolved.

    PowerPoint often splits one token across several runs. The value goes into the
    run holding most of the token name so it keeps that run's font.
    """
    unresolved: list[str] = []
    search_from = 0
    while True:
        runs = p_elem.findall(qn("a:r"))
        texts = [_run_text(r) for r in runs]
        full = "".join(texts)
        match = TOKEN_RE.search(full, search_from)
        if match is None:
            return unresolved

        key, fmt = split_token(match.group(1))
        if key not in values:
            unresolved.append(match.group(0))
            search_from = match.end()
            continue
        value = render_value(values[key], fmt)

        spans = []
        offset = 0
        for run, run_text in zip(runs, texts):
            spans.append((run, run_text, offset, offset + len(run_text)))
            offset += len(run_text)
        overlapping = [s for s in spans if s[2] < match.end() and s[3] > match.start()]

        def token_chars(span) -> int:
            _, run_text, start, end = span
            part = run_text[max(match.start(), start) - start : min(match.end(), end) - start]
            return len(re.sub(r"[{}\s]", "", part))

        style_run = max(overlapping, key=token_chars)[0]
        for run, run_text, start, end in overlapping:
            cut_from = max(match.start(), start) - start
            cut_to = min(match.end(), end) - start
            inserted = value if run is style_run else ""
            _set_run_text(run, run_text[:cut_from] + inserted + run_text[cut_to:])

        search_from = match.start() + len(value)


def replace_tokens_in_text_frame(text_frame, values: Mapping[str, TokenValue]) -> list[str]:
    unresolved: list[str] = []
    for paragraph in text_frame.paragraphs:
        unresolved.extend(replace_tokens_in_paragraph(paragraph._p, values))
    return unresolved


def find_tokens(text: str) -> list[str]:
    return [m.group(0) for m in TOKEN_RE.finditer(text or "")]


def iter_shapes(shapes: Iterable) -> Iterator:
    """Every shape on a slide, descending into groups."""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(shape.shapes)
        else:
            yield shape


def iter_text_frames(shapes: Iterable) -> Iterator:
    """Text frames of shapes and of every table cell, including grouped shapes."""
    for shape in iter_shapes(shapes):
        if shape.has_text_frame:
            yield shape.text_frame
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    yield cell.text_frame


def replace_tokens_in_shapes(shapes: Iterable, values: Mapping[str, TokenValue]) -> list[str]:
    unresolved: list[str] = []
    for text_frame in iter_text_frames(shapes):
        unresolved.extend(replace_tokens_in_text_frame(text_frame, values))
    return unresolved


def tokens_in_shapes(shapes: Iterable) -> list[str]:
    found: list[str] = []
    for text_frame in iter_text_frames(shapes):
        found.extend(find_tokens(text_frame.text))
    return found
