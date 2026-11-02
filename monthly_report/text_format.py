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


def uniform_run_fonts_in_row(table, row_index: int, *, ref_col: int = 1) -> None:
    """Make numeric cells in a table row use the same font as ``ref_col``."""
    if row_index >= len(table.rows):
        return
    ref_cell = table.cell(row_index, ref_col)
    ref_run = None
    for paragraph in ref_cell.text_frame.paragraphs:
        for run in paragraph.runs:
            if run.text.strip():
                ref_run = run
                break
        if ref_run is not None:
            break
    if ref_run is None:
        return

    for col_idx in range(len(table.columns)):
        if col_idx == ref_col:
            continue
        cell = table.cell(row_index, col_idx)
        for paragraph in cell.text_frame.paragraphs:
            for run in paragraph.runs:
                if run.text.strip():
                    copy_run_properties(run, ref_run)
