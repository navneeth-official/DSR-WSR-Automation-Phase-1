"""``{{Token}}`` replacement that keeps the template's run formatting."""

from __future__ import annotations

import re
from collections.abc import Mapping

from lxml import etree
from pptx.oxml.ns import qn

TOKEN_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_NUMBERED_TOKEN_RE = re.compile(r"^(sprint name|sprint)\s*\d+$")


def token_key(raw: str) -> str:
    """``Sprint Name 1`` -> ``sprint_name``, ``Start date`` -> ``start_date``, ``TC`` -> ``tc``."""
    key = re.sub(r"\s+", " ", raw.strip().lower())
    numbered = _NUMBERED_TOKEN_RE.match(key)
    if numbered:
        key = numbered.group(1)
    return key.replace(" ", "_")


def _run_text(run) -> str:
    t = run.find(qn("a:t"))
    return (t.text or "") if t is not None else ""


def _set_run_text(run, value: str) -> None:
    t = run.find(qn("a:t"))
    if t is None:
        t = etree.SubElement(run, qn("a:t"))
    t.text = value


def replace_tokens_in_paragraph(p_elem, values: Mapping[str, str]) -> list[str]:
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

        key = token_key(match.group(1))
        if key not in values:
            unresolved.append(match.group(0))
            search_from = match.end()
            continue
        value = values[key]

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


def replace_tokens_in_text_frame(text_frame, values: Mapping[str, str]) -> list[str]:
    unresolved: list[str] = []
    for paragraph in text_frame.paragraphs:
        unresolved.extend(replace_tokens_in_paragraph(paragraph._p, values))
    return unresolved


def find_tokens(text: str) -> list[str]:
    return [m.group(0) for m in TOKEN_RE.finditer(text or "")]
