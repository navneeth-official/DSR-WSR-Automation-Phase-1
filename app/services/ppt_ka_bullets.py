"""Key Activities bullet formatting — round • at list level 0 on all templates."""

from __future__ import annotations

import copy

from pptx.oxml import parse_xml
from pptx.oxml.ns import qn

from app.constants.ppt_bullets import KA_BULLET_CHAR, KA_BULLET_LEVEL


def _set_single_run_text(p_elem, text: str) -> None:
    runs = p_elem.findall(qn("a:r"))
    if not runs:
        return
    runs[0].find(qn("a:t")).text = text
    for extra in runs[1:]:
        p_elem.remove(extra)


def normalize_ka_bullet_template(p_elem) -> None:
    """Force lvl-0 round bullet (•) — G10X Key Activities style, not HL dash stories."""
    ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    for run in p_elem.findall(qn("a:r")):
        r_pr = run.find(qn("a:rPr"))
        if r_pr is not None and r_pr.get("b") == "1":
            r_pr.set("b", "0")

    p_pr = p_elem.find(qn("a:pPr"))
    if p_pr is None:
        p_pr = parse_xml(f'<a:pPr xmlns:a="{ns}"/>')
        p_elem.insert(0, p_pr)
    p_pr.set("lvl", str(KA_BULLET_LEVEL))
    for tag in ("a:buNone", "a:buAutoNum", "a:buBlip"):
        el = p_pr.find(qn(tag))
        if el is not None:
            p_pr.remove(el)

    bu = p_pr.find(qn("a:buChar"))
    if bu is None:
        p_pr.append(parse_xml(f'<a:buChar xmlns:a="{ns}" char="{KA_BULLET_CHAR}"/>'))
    else:
        bu.set("char", KA_BULLET_CHAR)


def replace_ka_bullet_block(txBody, first_index: int, last_index: int, items: list[str]) -> None:
    """Replace a KA bullet paragraph block preserving round-bullet formatting."""
    all_p = txBody.findall(qn("a:p"))
    template_p = all_p[first_index]
    block = all_p[first_index : last_index + 1]
    anchor = block[-1]

    new_paragraphs = []
    for text in items:
        new_p = copy.deepcopy(template_p)
        _set_single_run_text(new_p, text)
        normalize_ka_bullet_template(new_p)
        new_paragraphs.append(new_p)

    prev = anchor
    for new_p in new_paragraphs:
        prev.addnext(new_p)
        prev = new_p

    for p in block:
        txBody.remove(p)


def ka_bullet_char(p_elem) -> str | None:
    p_pr = p_elem.find(qn("a:pPr"))
    if p_pr is None:
        return None
    bu = p_pr.find(qn("a:buChar"))
    return bu.get("char") if bu is not None else None
