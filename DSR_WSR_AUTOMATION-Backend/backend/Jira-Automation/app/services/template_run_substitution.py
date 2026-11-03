"""Replace {placeholders} without discarding the run that carries their formatting."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pptx.oxml.ns import qn

from app.services.template_placeholders import PlaceholderContext

_TOKEN_RE = re.compile(r"\{([^{}]+)\}")


def _run_text(run) -> str:
    return "".join((node.text or "") for node in run.findall(qn("a:t")))


def _set_run_text(run, text: str) -> None:
    nodes = run.findall(qn("a:t"))
    if not nodes:
        return
    nodes[0].text = text
    for extra in nodes[1:]:
        extra.text = ""


@dataclass
class RunSpan:
    text: str
    run_elem: object


def paragraph_plain_text(p_elem) -> str:
    return "".join(_run_text(run) for run in p_elem.findall(qn("a:r")))


def paragraph_run_spans(p_elem) -> tuple[str, list[RunSpan]]:
    spans = [RunSpan(_run_text(run), run) for run in p_elem.findall(qn("a:r"))]
    return "".join(span.text for span in spans), spans


def substitute_text(template: str, ctx: PlaceholderContext) -> str:
    def replace(match: re.Match[str]) -> str:
        value = ctx.resolve(match.group(1), preceding=template[: match.start()])
        if value is None:
            return match.group(0)
        return value

    return _TOKEN_RE.sub(replace, template or "")


def substitute_placeholders_in_paragraph(p_elem, ctx: PlaceholderContext) -> bool:
    runs = [run for run in p_elem.findall(qn("a:r")) if run.findall(qn("a:t"))]
    pieces = [_run_text(run) for run in runs]
    full = "".join(pieces)
    matches = list(_TOKEN_RE.finditer(full))
    if not matches:
        return False

    owners: list[int] = []
    for index, text in enumerate(pieces):
        owners.extend([index] * len(text))
    rebuilt = [[] for _ in runs]
    changed = False
    cursor = 0
    for match in matches:
        for index in range(cursor, match.start()):
            rebuilt[owners[index]].append(full[index])
        value = ctx.resolve(match.group(1), preceding=full[: match.start()])
        if value is None:
            for index in range(match.start(), match.end()):
                rebuilt[owners[index]].append(full[index])
        else:
            changed = True
            owner = owners[match.start()]
            for index in range(match.start() + 1, match.end() - 1):
                if not full[index].isspace():
                    owner = owners[index]
                    break
            rebuilt[owner].append(value)
        cursor = match.end()
    for index in range(cursor, len(full)):
        rebuilt[owners[index]].append(full[index])

    if not changed:
        return False
    for run, parts in zip(runs, rebuilt):
        _set_run_text(run, "".join(parts))
    return True
