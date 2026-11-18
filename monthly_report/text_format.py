"""Copy paragraph/run formatting when filling template placeholders."""

from __future__ import annotations

from copy import deepcopy

from pptx.oxml.ns import qn


def copy_paragraph_properties(dst_paragraph, src_paragraph) -> None:
    src_ppr = src_paragraph._p.find(qn("a:pPr"))
    if src_ppr is None:
        return
    dst_p = dst_paragraph._p
    existing = dst_p.find(qn("a:pPr"))
    if existing is not None:
        dst_p.remove(existing)
    dst_p.insert(0, deepcopy(src_ppr))


def copy_run_properties(dst_run, src_run) -> None:
    src_rpr = src_run._r.find(qn("a:rPr"))
    if src_rpr is None:
        return
    dst_r = dst_run._r
    existing = dst_r.find(qn("a:rPr"))
    if existing is not None:
        dst_r.remove(existing)
    dst_r.insert(0, deepcopy(src_rpr))
