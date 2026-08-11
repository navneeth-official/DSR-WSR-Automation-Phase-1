"""Semantic slide-type detection for WSR templates."""

from __future__ import annotations

import re

from pptx.slide import Slide

from app.services.ppt_shape_utils import (
    get_highlights_shape,
    get_key_activities_shape,
    has_combined_hl_ka_table,
    is_contd_title,
    is_delivery_slide_title,
    normalize_title_text,
    service_suffix_from_title,
    slide_title_text,
)
from app.wsr_engine.models import ProjectMap, SlideDescriptor, TitleFormat


def _looks_like_index_slide(slide: Slide) -> bool:
    for shape in slide.shapes:
        if not shape.has_table:
            continue
        table = shape.table
        numeric_cells = 0
        label_cells = 0
        for row in table.rows:
            for cell in row.cells:
                text = normalize_title_text(cell.text_frame.text)
                if not text:
                    continue
                if text.isdigit() or (len(text) <= 2 and text.replace("\u200b", "").isdigit()):
                    numeric_cells += 1
                elif len(text) > 3:
                    label_cells += 1
        if numeric_cells >= 2 and label_cells >= 2:
            return True
    return False


def _slide_has_ka_body(slide: Slide) -> bool:
    if get_key_activities_shape(slide) is not None:
        return True
    return has_combined_hl_ka_table(slide)


def _slide_has_highlights(slide: Slide) -> bool:
    try:
        get_highlights_shape(slide)
        return True
    except ValueError:
        return False


def classify_slide(slide: Slide, index: int) -> SlideDescriptor:
    title = slide_title_text(slide)
    norm = normalize_title_text(title).lower()

    if index == 0 or "weekly status report" in norm:
        return SlideDescriptor(index=index, title=title, slide_type="COVER")

    if norm == "index" or _looks_like_index_slide(slide):
        return SlideDescriptor(index=index, title=title or "Index", slide_type="INDEX")

    has_hl = _slide_has_highlights(slide)
    has_ka = _slide_has_ka_body(slide)

    if is_delivery_slide_title(title):
        project = service_suffix_from_title(title)
        if is_contd_title(title):
            return SlideDescriptor(
                index=index,
                title=title,
                slide_type="PROJECT_CONTINUATION",
                project_name=project,
                has_highlights=has_hl,
                has_ka=has_ka,
            )
        if has_hl:
            return SlideDescriptor(
                index=index,
                title=title,
                slide_type="PROJECT_MAIN",
                project_name=project,
                has_highlights=True,
                has_ka=has_ka,
            )
        if has_ka and not has_hl:
            return SlideDescriptor(
                index=index,
                title=title,
                slide_type="PROJECT_KA",
                project_name=project,
                has_ka=True,
            )

    return SlideDescriptor(
        index=index,
        title=title,
        slide_type="OTHER",
        has_highlights=has_hl,
        has_ka=has_ka,
    )


def build_project_maps(slides: list[SlideDescriptor]) -> list[ProjectMap]:
    projects: dict[str, ProjectMap] = {}
    order: list[str] = []

    for desc in slides:
        if desc.slide_type == "PROJECT_MAIN" and desc.project_name:
            name = desc.project_name
            if name not in projects:
                projects[name] = ProjectMap(project_name=name, main_slide_index=desc.index)
                order.append(name)
            else:
                projects[name].main_slide_index = desc.index

        elif desc.slide_type == "PROJECT_CONTINUATION" and desc.project_name:
            name = desc.project_name
            if name not in projects:
                projects[name] = ProjectMap(project_name=name, main_slide_index=desc.index)
                order.append(name)
            projects[name].continuation_indices.append(desc.index)

        elif desc.slide_type == "PROJECT_KA" and desc.project_name:
            name = desc.project_name
            if name not in projects:
                projects[name] = ProjectMap(project_name=name, main_slide_index=desc.index)
                order.append(name)
            projects[name].ka_slide_index = desc.index

    return [projects[name] for name in order if name in projects]


def detect_contd_marker(title: str) -> str:
    """Extract contd marker from an existing title."""
    m = re.search(r"(\(contd[^)]*\))", title, re.IGNORECASE)
    if m:
        return m.group(1)
    return "(Contd..)"


def detect_title_format(slides: list[SlideDescriptor]) -> TitleFormat:
    """Detect delivery-status title casing, separator, and contd marker from template."""
    prefix = "Delivery Status"
    separator = " - "
    contd_marker = "(Contd..)"

    for desc in slides:
        title = desc.title
        if not is_delivery_slide_title(title):
            continue
        lower = title.lower()
        idx = lower.find("delivery status")
        if idx >= 0:
            prefix = title[idx : idx + len("Delivery Status")]
            if title[idx + len("Delivery Status") : idx + len("Delivery Status") + 1] == "s":
                prefix = title[idx : idx + len("Delivery status")]

        for sep in (" \u2013 ", " - ", "-"):
            if sep in title:
                separator = sep
                break

        if is_contd_title(title):
            contd_marker = detect_contd_marker(title)
        break

    return TitleFormat(prefix=prefix, separator=separator, contd_marker=contd_marker)
