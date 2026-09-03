"""Run-level placeholder substitution preserving PowerPoint formatting."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from pptx.oxml import parse_xml
from pptx.oxml.ns import qn

from app.services.ppt_shape_utils import paragraph_text
from app.services.template_placeholders import (
    PlaceholderContext,
    _PLACEHOLDER_TOKEN_RE,
    find_placeholder_tokens,
    normalize_token_name,
)

_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


@dataclass
class RunSpan:
    run_elem: object
    start: int
    end: int
    text: str


def _run_text(run_elem) -> str:
    t_elem = run_elem.find(qn("a:t"))
    return (t_elem.text if t_elem is not None else None) or ""


def _set_run_text(run_elem, text: str) -> None:
    t_elem = run_elem.find(qn("a:t"))
    if t_elem is None:
        t_elem = parse_xml(f'<a:t xmlns:a="{_NS}"/>')
        run_elem.append(t_elem)
    t_elem.text = text


def paragraph_run_spans(p_elem) -> tuple[str, list[RunSpan]]:
    """Coalesce paragraph runs into full text with run boundary map."""
    runs = p_elem.findall(qn("a:r"))
    full_parts: list[str] = []
    spans: list[RunSpan] = []
    offset = 0
    for run in runs:
        text = _run_text(run)
        start = offset
        end = offset + len(text)
        spans.append(RunSpan(run_elem=run, start=start, end=end, text=text))
        full_parts.append(text)
        offset = end
    return "".join(full_parts), spans


def substitute_text(text: str, context: PlaceholderContext) -> str:
    """Replace all {Token} occurrences in a string."""

    def repl(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        value = context.resolve(raw)
        if value is None:
            return match.group(0)
        return value

    return _PLACEHOLDER_TOKEN_RE.sub(repl, text or "")


def _overlapping_spans(spans: list[RunSpan], start: int, end: int) -> list[RunSpan]:
    return [s for s in spans if s.start < end and s.end > start]


def _style_run_for_token(overlapping: list[RunSpan], token_raw: str) -> RunSpan:
    """
    Pick the run whose rPr should apply to the substituted value.

    When PowerPoint splits ``{ From Date }`` across runs (``{ ``, ``From Date``,
    `` }``), the distinctive font usually lives on the token-name run — not the
    brace runs.
    """
    token_key = normalize_token_name(token_raw)
    for span in overlapping:
        inner = re.sub(r"[{}\s]", "", span.text)
        if inner and normalize_token_name(inner) == token_key:
            return span

    def _content_score(span: RunSpan) -> int:
        return len(re.sub(r"[{}\s]", "", span.text))

    return max(overlapping, key=_content_score)


def substitute_placeholders_in_paragraph(p_elem, context: PlaceholderContext) -> bool:
    """
    Replace {Token} placeholders in a paragraph, preserving run properties.

    Placeholders may span multiple runs (common when each token fragment has its
    own font). The substituted value inherits formatting from the token-name run.
    """
    changed = False
    while True:
        full_text, spans = paragraph_run_spans(p_elem)
        match = _PLACEHOLDER_TOKEN_RE.search(full_text)
        if not match:
            break

        token_raw = match.group(1).strip()
        value = context.resolve(token_raw)
        if value is None:
            break

        overlapping = _overlapping_spans(spans, match.start(), match.end())
        if not overlapping:
            break

        if len(overlapping) == 1:
            span = overlapping[0]
            local_start = match.start() - span.start
            local_end = match.end() - span.start
            new_text = span.text[:local_start] + value + span.text[local_end:]
            _set_run_text(span.run_elem, new_text)
        else:
            style = _style_run_for_token(overlapping, token_raw)
            _set_run_text(style.run_elem, value)
            for span in overlapping:
                if span.run_elem is style.run_elem:
                    continue
                local_start = max(match.start(), span.start) - span.start
                local_end = min(match.end(), span.end) - span.start
                new_text = span.text[:local_start] + span.text[local_end:]
                _set_run_text(span.run_elem, new_text)

        changed = True

    return changed


def substitute_placeholders_in_shape_text_frame(shape, context: PlaceholderContext) -> bool:
    """Substitute placeholders in every paragraph of a shape or table cell."""
    text_frame = getattr(shape, "text_frame", None)
    if text_frame is None:
        return False
    changed = False
    for paragraph in text_frame.paragraphs:
        if substitute_placeholders_in_paragraph(paragraph._p, context):
            changed = True
    return changed


def clone_paragraph_with_substitution(p_elem, context: PlaceholderContext):
    """Deep-copy a paragraph and substitute placeholders."""
    cloned = copy.deepcopy(p_elem)
    substitute_placeholders_in_paragraph(cloned, context)
    return cloned


def _set_run_bold(run_elem, bold: bool) -> None:
    r_pr = run_elem.find(qn("a:rPr"))
    if r_pr is None:
        r_pr = parse_xml(f'<a:rPr xmlns:a="{_NS}"/>')
        run_elem.insert(0, r_pr)
    if bold:
        r_pr.set("b", "1")
    elif r_pr.get("b") is not None:
        r_pr.set("b", "0")


def normalize_sprint_line_bold_runs(p_elem) -> None:
    """Bold sprint title/status; keep dates and story-count stats regular (template)."""
    full_text, spans = paragraph_run_spans(p_elem)
    paren_at = full_text.find("(")
    if paren_at < 0:
        return
    for span in spans:
        if span.end <= paren_at:
            _set_run_bold(span.run_elem, True)
        else:
            _set_run_bold(span.run_elem, False)


def normalize_story_line_runs(p_elem) -> None:
    """Collapse story body into one run so stray font splits cannot linger."""
    from app.services.ppt_hl_bullets import (
        _story_prefix_content_runs,
        set_single_run_text,
    )

    full_text = paragraph_text(p_elem).strip()
    if not full_text:
        return
    prefix_runs = _story_prefix_content_runs(p_elem)
    if prefix_runs is not None:
        _, content_run = prefix_runs
        body = full_text.lstrip("".join(("-", "\u2013", "\u208b"))).strip()
        content_run.find(qn("a:t")).text = f"\t{body}"
        runs = p_elem.findall(qn("a:r"))
        idx = runs.index(content_run)
        for extra in runs[idx + 1 :]:
            p_elem.remove(extra)
        return
    set_single_run_text(p_elem, full_text)


def paragraph_plain_text(p_elem) -> str:
    return paragraph_text(p_elem).strip()
