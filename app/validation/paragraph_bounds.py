"""Resolve slide coordinates for a Highlights paragraph (COM or estimated)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.rendering.com_text_bounds import POINTS_PER_INCH

DEFAULT_LINE_SPACING_PT = 15.3


def _normalize_text(text: str) -> str:
    return " ".join((text or "").replace("\t", " ").split()).strip()


def _first_filled_paragraph_index(paragraphs: list[dict[str, Any]]) -> int:
    for index, para in enumerate(paragraphs):
        if (para.get("text") or "").strip() and para.get("role") != "blank":
            return index
    return 0


def _text_anchor_top_in(slide_data: dict[str, Any]) -> float | None:
    """Top of the first visible HL text line on the slide."""
    text_top = slide_data.get("hl_text_top_in")
    if text_top is not None:
        return float(text_top)

    content_top = slide_data.get("hl_content_top_in")
    if content_top is None:
        hl_pos = (slide_data.get("highlights") or {}).get("position_in") or {}
        content_top = hl_pos.get("top")
    if content_top is None:
        return None

    waste_above = float(slide_data.get("hl_waste_above_text_in") or 0.0)
    return float(content_top) + waste_above


def _match_paragraph(
    paragraphs: list[dict[str, Any]],
    *,
    paragraph_index: int | None,
    text: str | None,
    role: str | None,
    paragraph_text: str | None = None,
) -> tuple[int, dict[str, Any]] | None:
    full_text = _normalize_text(paragraph_text or "")
    if full_text:
        for index, para in enumerate(paragraphs):
            para_text = _normalize_text(para.get("text") or "")
            if not para_text:
                continue
            if role and str(para.get("role") or "") != role:
                continue
            if full_text == para_text or full_text in para_text or para_text.startswith(full_text[:24]):
                return index, para

    if paragraph_index is not None and 0 <= paragraph_index < len(paragraphs):
        para = paragraphs[paragraph_index]
        if (para.get("text") or "").strip():
            return paragraph_index, para

    needle = _normalize_text(text or "")
    role = str(role or "")
    if len(needle) < 8:
        return None
    for index, para in enumerate(paragraphs):
        para_text = _normalize_text(para.get("text") or "")
        if not para_text:
            continue
        if role and str(para.get("role") or "") != role:
            continue
        if needle in para_text or para_text.startswith(needle[: min(24, len(needle))]):
            return index, para
    return None


def _match_com_rect(
    com_rects: list[dict[str, Any]],
    detail: dict[str, Any],
) -> dict[str, float] | None:
    paragraph_text = _normalize_text(str(detail.get("paragraph_text") or ""))
    role = str(detail.get("role") or "")

    if paragraph_text:
        for rect in com_rects:
            rect_text = _normalize_text(str(rect.get("text") or ""))
            if not rect_text:
                continue
            if paragraph_text == rect_text or paragraph_text in rect_text or rect_text.startswith(paragraph_text[:24]):
                return rect

    run_text = _normalize_text(str(detail.get("text") or ""))
    if len(run_text) >= 8:
        for rect in com_rects:
            rect_text = _normalize_text(str(rect.get("text") or ""))
            if run_text in rect_text or rect_text.startswith(run_text[:24]):
                return rect

    paragraph_index = detail.get("paragraph_index")
    if isinstance(paragraph_index, int):
        for rect in com_rects:
            if rect.get("paragraph_index") == paragraph_index:
                return rect

    if role and paragraph_text:
        for rect in com_rects:
            rect_text = _normalize_text(str(rect.get("text") or ""))
            if role == "current_week" and paragraph_text:
                if paragraph_text == rect_text or paragraph_text in rect_text or rect_text.startswith(paragraph_text[:24]):
                    return rect
            if role == "story_item" and rect_text.startswith(("₋", "-", "–", "—")):
                if paragraph_text and paragraph_text[-20:] in rect_text:
                    return rect
    return None


def _is_run_level_detail(detail: dict[str, Any]) -> bool:
    issue = str(detail.get("issue") or "")
    if issue not in {"wrong_font", "wrong_size", "not_bold", "unexpected_bold"}:
        return False
    run_text = _normalize_text(str(detail.get("text") or ""))
    paragraph_text = _normalize_text(str(detail.get("paragraph_text") or ""))
    if not run_text or not paragraph_text or run_text == paragraph_text:
        return False
    if len(run_text) >= len(paragraph_text):
        return False
    return run_text.lower() in paragraph_text.lower()


def _bullet_indent_in(level: int) -> float:
    return 0.18 + max(level, 0) * 0.18


def estimate_hl_run_rect_in(
    slide_data: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, float] | None:
    """Estimate bounds for a specific run/word inside a paragraph line."""
    if not _is_run_level_detail(detail):
        return None

    paragraph_rect = estimate_hl_paragraph_rect_in(
        slide_data,
        paragraph_index=detail.get("paragraph_index") if isinstance(detail.get("paragraph_index"), int) else None,
        text=str(detail.get("paragraph_text") or ""),
        role=str(detail.get("role") or ""),
        paragraph_text=str(detail.get("paragraph_text") or ""),
    )
    if paragraph_rect is None:
        return None

    hl = slide_data.get("highlights") or {}
    paragraphs = hl.get("paragraphs") or []
    matched = _match_paragraph(
        paragraphs,
        paragraph_index=detail.get("paragraph_index") if isinstance(detail.get("paragraph_index"), int) else None,
        text=str(detail.get("paragraph_text") or ""),
        role=str(detail.get("role") or ""),
        paragraph_text=str(detail.get("paragraph_text") or ""),
    )
    if matched is None:
        return None
    _, para = matched

    run_needle = _normalize_text(str(detail.get("text") or ""))
    para_text = para.get("text") or ""
    runs = para.get("runs") or []

    offset = 0
    run_len = len(run_needle)
    matched_run: dict[str, Any] | None = None
    for run in runs:
        run_text = run.get("text") or ""
        norm = _normalize_text(run_text)
        if run_needle.lower() in norm.lower() or norm.lower() in run_needle.lower():
            matched_run = run
            run_len = max(len(norm), len(run_needle))
            break
        offset += len(run_text)

    if matched_run is None:
        idx = para_text.lower().find(run_needle.lower())
        if idx < 0:
            return None
        offset = idx
        run_len = len(run_needle)

    total_len = max(len(para_text), 1)
    level = int(para.get("level") or 0)
    line_left = float(paragraph_rect["left_in"]) + _bullet_indent_in(level)
    line_width = max(float(paragraph_rect["width_in"]) - _bullet_indent_in(level), 0.5)
    run_left = line_left + (offset / total_len) * line_width
    run_width = max((run_len / total_len) * line_width, 0.15)

    size_pt = matched_run.get("size_pt") if matched_run else detail.get("size_pt")
    height = float(size_pt or DEFAULT_LINE_SPACING_PT) / POINTS_PER_INCH
    top = float(paragraph_rect["top_in"]) + 0.01
    if matched_run and size_pt and paragraph_rect.get("height_in"):
        # Larger-than-line runs extend upward within the line box.
        line_h = float(paragraph_rect["height_in"])
        top = float(paragraph_rect["top_in"]) + max(line_h - height, 0.0) / 2

    return {
        "left_in": round(run_left, 4),
        "top_in": round(top, 4),
        "width_in": round(run_width, 4),
        "height_in": round(max(height, 0.08), 4),
    }


def measure_hl_run_rect_com(
    ppt_path: Path,
    slide_index: int,
    *,
    paragraph_text: str,
    run_text: str,
) -> dict[str, float] | None:
    """Return rendered bounds for a word/run inside an HL paragraph via COM."""
    from app.rendering.com_text_bounds import ComTextBoundsMeasurer, _iter_hl_shapes

    needle = _normalize_text(run_text)
    para_needle = _normalize_text(paragraph_text)
    if not needle or not para_needle:
        return None

    with ComTextBoundsMeasurer(ppt_path) as measurer:
        slide = measurer._presentation.Slides(slide_index)
        hl_shape = next(_iter_hl_shapes(slide), None)
        if hl_shape is None:
            return None

        cell_shape = hl_shape.Table.Cell(3, 1).Shape
        text_range = None
        for accessor in ("TextFrame", "TextFrame2"):
            try:
                text_range = getattr(cell_shape, accessor).TextRange
                break
            except Exception:
                continue
        if text_range is None:
            return None

        try:
            para_count = int(text_range.Paragraphs().Count)
        except Exception:
            return None

        for para_index in range(1, para_count + 1):
            try:
                para = text_range.Paragraphs(para_index)
            except Exception:
                continue
            text = _normalize_text(str(para.Text or ""))
            if not text:
                continue
            if para_needle not in text and not text.startswith(para_needle[:24]):
                continue

            found = None
            try:
                found = para.Find(needle.strip())
            except Exception:
                found = None
            if found is None:
                raw = str(para.Text or "")
                idx = raw.lower().find(needle.lower())
                if idx < 0:
                    continue
                try:
                    start = int(para.Start) + idx
                    found = text_range.Characters(start + 1, len(needle.strip()))
                except Exception:
                    continue

            try:
                rel_top = float(found.BoundTop)
                rel_left = float(found.BoundLeft)
                rel_width = float(found.BoundWidth)
                rel_height = float(found.BoundHeight)
            except Exception:
                continue

            return {
                "left_in": round((float(cell_shape.Left) + rel_left) / POINTS_PER_INCH, 4),
                "top_in": round((float(cell_shape.Top) + rel_top) / POINTS_PER_INCH, 4),
                "width_in": round(max(rel_width / POINTS_PER_INCH, 0.08), 4),
                "height_in": round(max(rel_height / POINTS_PER_INCH, 0.08), 4),
            }
    return None


def estimate_hl_paragraph_rect_in(
    slide_data: dict[str, Any],
    *,
    paragraph_index: int | None = None,
    text: str | None = None,
    role: str | None = None,
    paragraph_text: str | None = None,
) -> dict[str, float] | None:
    """Estimate a paragraph bounding box inside the Highlights content cell."""
    hl = slide_data.get("highlights") or {}
    hl_pos = hl.get("position_in") or {}
    paragraphs = hl.get("paragraphs") or []
    matched = _match_paragraph(
        paragraphs,
        paragraph_index=paragraph_index,
        text=text,
        role=role,
        paragraph_text=paragraph_text,
    )
    if matched is None:
        return None
    target_index, para = matched

    text_anchor = _text_anchor_top_in(slide_data)
    if text_anchor is None:
        return None

    left = float(hl_pos.get("left") or 0.12) + 0.08
    width = max(float(hl_pos.get("width") or 8.0) - 0.16, 1.0)

    first_filled = _first_filled_paragraph_index(paragraphs)
    top = float(text_anchor)
    for index, item in enumerate(paragraphs):
        if index >= target_index:
            break
        if index < first_filled:
            continue
        item_text = (item.get("text") or "").strip()
        if not item_text or item.get("role") == "blank":
            continue
        spacing_pt = float(item.get("line_spacing_pt") or DEFAULT_LINE_SPACING_PT)
        top += spacing_pt / POINTS_PER_INCH

    spacing_pt = float(para.get("line_spacing_pt") or DEFAULT_LINE_SPACING_PT)
    height = spacing_pt / POINTS_PER_INCH
    pad = 0.025
    return {
        "left_in": round(left, 4),
        "top_in": round(top - pad, 4),
        "width_in": round(width, 4),
        "height_in": round(height + 2 * pad, 4),
    }


def measure_hl_paragraph_rects_com(
    ppt_path: Path,
    slide_index: int,
) -> list[dict[str, Any]]:
    """Return rendered bounds (inches) for each non-empty HL paragraph via COM."""
    from app.rendering.com_text_bounds import ComTextBoundsMeasurer, _iter_hl_shapes

    rects: list[dict[str, Any]] = []
    with ComTextBoundsMeasurer(ppt_path) as measurer:
        slide = measurer._presentation.Slides(slide_index)
        hl_shape = next(_iter_hl_shapes(slide), None)
        if hl_shape is None:
            return rects

        cell_shape = hl_shape.Table.Cell(3, 1).Shape
        text_range = None
        for accessor in ("TextFrame2", "TextFrame"):
            try:
                text_range = getattr(cell_shape, accessor).TextRange
                break
            except Exception:
                continue
        if text_range is None:
            return rects

        content_left_in = round(float(hl_shape.Left) / POINTS_PER_INCH, 4)
        content_right_in = round(
            (float(hl_shape.Left) + float(hl_shape.Width)) / POINTS_PER_INCH, 4
        )

        try:
            paras = text_range.Paragraphs()
            count = int(paras.Count)
        except Exception:
            return rects

        for para_index in range(1, count + 1):
            try:
                para = text_range.Paragraphs(para_index)
            except Exception:
                continue
            text = str(para.Text or "").strip()
            if not text:
                continue
            try:
                rel_top = float(para.BoundTop)
                rel_height = float(para.BoundHeight)
            except Exception:
                continue
            abs_top_in = round((float(cell_shape.Top) + rel_top) / POINTS_PER_INCH, 4)
            abs_bottom_in = round(
                (float(cell_shape.Top) + rel_top + rel_height) / POINTS_PER_INCH, 4
            )
            rects.append(
                {
                    "paragraph_index": para_index - 1,
                    "text": text,
                    "left_in": content_left_in + 0.08,
                    "top_in": abs_top_in - 0.02,
                    "width_in": max(content_right_in - content_left_in - 0.16, 1.0),
                    "height_in": max(abs_bottom_in - abs_top_in + 0.04, 0.08),
                }
            )
    return rects


def estimate_hl_paragraph_rect_by_index(
    slide_data: dict[str, Any],
    target_index: int,
) -> dict[str, float] | None:
    """Estimate bounds for any HL paragraph index, including blank spacer lines."""
    hl = slide_data.get("highlights") or {}
    hl_pos = hl.get("position_in") or {}
    paragraphs = hl.get("paragraphs") or []
    if target_index < 0 or target_index >= len(paragraphs):
        return None

    text_anchor = _text_anchor_top_in(slide_data)
    if text_anchor is None:
        return None

    left = float(hl_pos.get("left") or 0.12) + 0.08
    width = max(float(hl_pos.get("width") or 8.0) - 0.16, 1.0)
    first_filled = _first_filled_paragraph_index(paragraphs)
    top = float(text_anchor)
    for index, item in enumerate(paragraphs):
        if index >= target_index:
            break
        if index < first_filled:
            continue
        spacing_pt = float(item.get("line_spacing_pt") or DEFAULT_LINE_SPACING_PT)
        top += spacing_pt / POINTS_PER_INCH

    para = paragraphs[target_index]
    spacing_pt = float(para.get("line_spacing_pt") or DEFAULT_LINE_SPACING_PT)
    height = spacing_pt / POINTS_PER_INCH
    pad = 0.025
    return {
        "left_in": round(left, 4),
        "top_in": round(top - pad, 4),
        "width_in": round(width, 4),
        "height_in": round(max(height + 2 * pad, 0.12), 4),
    }


def merge_hl_bounds_in(bounds_list: list[dict[str, float]]) -> dict[str, float] | None:
    """Merge adjacent paragraph bounds into one visual region."""
    if not bounds_list:
        return None
    if len(bounds_list) == 1:
        return bounds_list[0]
    left = min(float(b["left_in"]) for b in bounds_list)
    top = min(float(b["top_in"]) for b in bounds_list)
    right = max(float(b["left_in"]) + float(b["width_in"]) for b in bounds_list)
    bottom = max(float(b["top_in"]) + float(b["height_in"]) for b in bounds_list)
    return {
        "left_in": round(left, 4),
        "top_in": round(top, 4),
        "width_in": round(right - left, 4),
        "height_in": round(bottom - top, 4),
    }


def resolve_hl_spacing_blank_regions(
    slide_data: dict[str, Any],
    detail: dict[str, Any],
    *,
    ppt_path: Path | None = None,
    slide_index: int | None = None,
) -> list[dict[str, float]]:
    """Return inch bounds for each extra blank spacer paragraph in a spacing violation."""
    del ppt_path, slide_index  # estimated layout is sufficient for empty paragraphs
    issue = str(detail.get("issue") or "")
    paragraphs = (slide_data.get("highlights") or {}).get("paragraphs") or []
    regions: list[dict[str, float]] = []

    if issue == "extra_blanks_after_current_week":
        start_index = detail.get("paragraph_index")
        extra = int(detail.get("blank_count") or 0)
        if not isinstance(start_index, int) or extra <= 0:
            return regions
        for offset in range(1, extra + 1):
            index = start_index + offset
            if index >= len(paragraphs) or paragraphs[index].get("role") != "blank":
                break
            bounds = estimate_hl_paragraph_rect_by_index(slide_data, index)
            if bounds:
                regions.append(bounds)
        return regions

    if issue == "extra_sprint_gap_blanks":
        sprint_index = detail.get("paragraph_index")
        extra = int(detail.get("blank_count") or 0)
        if not isinstance(sprint_index, int) or extra <= 0:
            return regions
        for offset in range(1, extra + 1):
            index = sprint_index - offset
            if index < 0 or paragraphs[index].get("role") != "blank":
                break
            bounds = estimate_hl_paragraph_rect_by_index(slide_data, index)
            if bounds:
                regions.insert(0, bounds)
        return regions

    return regions


def resolve_hl_paragraph_rect_in(
    slide_data: dict[str, Any],
    detail: dict[str, Any],
    *,
    ppt_path: Path | None = None,
    slide_index: int | None = None,
) -> dict[str, float] | None:
    """Best-effort bounds for a typography violation (run/word or whole line)."""
    paragraph_text = detail.get("paragraph_text")
    run_is_substring = _is_run_level_detail(detail)

    if run_is_substring and ppt_path is not None and slide_index is not None:
        try:
            run_rect = measure_hl_run_rect_com(
                ppt_path,
                slide_index,
                paragraph_text=str(paragraph_text or ""),
                run_text=str(detail.get("text") or ""),
            )
            if run_rect:
                return run_rect
        except Exception:
            pass

    if run_is_substring:
        estimated_run = estimate_hl_run_rect_in(slide_data, detail)
        if estimated_run:
            return estimated_run

    paragraph_index = detail.get("paragraph_index")
    text = detail.get("text") or detail.get("paragraph_text")
    role = detail.get("role")

    if ppt_path is not None and slide_index is not None:
        try:
            com_rects = measure_hl_paragraph_rects_com(ppt_path, slide_index)
            matched = _match_com_rect(com_rects, detail)
            if matched:
                return matched
        except Exception:
            pass

    return estimate_hl_paragraph_rect_in(
        slide_data,
        paragraph_index=paragraph_index if isinstance(paragraph_index, int) else None,
        text=str(text) if text else None,
        role=str(role) if role else None,
        paragraph_text=str(paragraph_text) if paragraph_text else None,
    )
