"""Wrap-aware Highlights / Key Activities layout — template-agnostic."""

from __future__ import annotations

import copy
import logging

from pptx import Presentation

from app.services.ppt_layout_metrics import (
    EMU_PER_INCH,
    FIXED_STORY_LINE_HEIGHT_EMU,
    FOOTER_MAX_BOTTOM_EMU,
    apply_fixed_story_line_metrics,
    count_hl_paragraphs,
    count_visual_lines_in_hl,
    estimated_text_bottom_emu,
    hl_ka_tab_gap_emu,
)
from app.services.ppt_shape_utils import get_highlights_shape, get_key_activities_shape
from app.services.template_profile import ServiceProfile, TemplateProfile
from app.wsr_engine.hl_ka_normalizer import find_standalone_reference_slide
from app.wsr_engine.overflow_engine import build_layout_profile

logger = logging.getLogger(__name__)

MAX_KA_BOTTOM_EMU = FOOTER_MAX_BOTTOM_EMU
MIN_HL_BOTTOM_PAD_EMU = int(0.1 * EMU_PER_INCH)
HL_CONTENT_BOTTOM_PAD_EMU = int(0.1 * EMU_PER_INCH)
_VISUAL_LINE_BUFFER = 1.12


def _canonical_per_line(profile: dict) -> int:
    return int(profile.get("canonical_per_line_emu") or FIXED_STORY_LINE_HEIGHT_EMU)


def _set_table_shape_height(hl_shape, row_heights: list[int], target_h: int) -> None:
    table = hl_shape.table
    for i, h in enumerate(row_heights):
        table.rows[i].height = h
    hl_shape.height = target_h


def _min_hl_height_for_content(hl_shape, profile: dict) -> int:
    """Minimum HL table height so wrap-aware text is not clipped."""
    r0, r1 = profile["r0"], profile["r1"]
    ref_pad = profile["ref_pad"]
    per_line = _canonical_per_line(profile)
    effective_lines = max(count_hl_paragraphs(hl_shape), count_visual_lines_in_hl(hl_shape))
    content_h = int(per_line * effective_lines * _VISUAL_LINE_BUFFER)
    return int(r0 + r1 + content_h + MIN_HL_BOTTOM_PAD_EMU)


def fit_hl_to_content(hl_shape, profile: dict, max_h: int | None = None) -> int:
    """
    Resize Highlights table to rendered text (+ small pad), never larger than required.

    Returns the applied table height in EMU.
    """
    r0, r1 = profile["r0"], profile["r1"]
    ref_r2 = profile["ref_r2"]
    ref_para_count = profile.get("canonical_para_count", profile["ref_para_count"])
    per_line = _canonical_per_line(profile)

    text_bottom = estimated_text_bottom_emu(
        hl_shape,
        ref_para_count=ref_para_count,
        ref_r2=ref_r2,
        per_line_emu=per_line,
    )
    min_h = _min_hl_height_for_content(hl_shape, profile)
    target_h = max(int(text_bottom - hl_shape.top + HL_CONTENT_BOTTOM_PAD_EMU), min_h)
    if max_h is not None:
        target_h = min(target_h, max_h)

    min_pad = MIN_HL_BOTTOM_PAD_EMU
    min_content_h = max(int(per_line * 1), 45720)
    content_h = max(target_h - r0 - r1 - min_pad, min_content_h)
    _set_table_shape_height(hl_shape, [r0, r1, content_h], target_h)
    return target_h


def hl_content_needs_ka_contd(hl_shape, profile: dict, ka_height_emu: int) -> bool:
    """True when HL content height cannot share the slide with KA above the footer."""
    needed = _min_hl_height_for_content(hl_shape, profile)
    gap = hl_ka_tab_gap_emu()
    allowed = int(MAX_KA_BOTTOM_EMU - ka_height_emu - gap - hl_shape.top)
    return needed > allowed


def hl_text_bottom_emu(hl_shape, profile: dict) -> int:
    """Wrap-aware text end using template line metrics (not inflated cell row height)."""
    return estimated_text_bottom_emu(
        hl_shape,
        ref_para_count=profile.get("canonical_para_count", profile["ref_para_count"]),
        ref_r2=profile["ref_r2"],
        per_line_emu=_canonical_per_line(profile),
    )


def effective_ka_top(hl_shape, profile: dict, ka_height: int) -> int:
    """KA top = HL table bottom + fixed tab gap (~2 story lines), footer-clamped."""
    gap = hl_ka_tab_gap_emu(profile.get("canonical_line_height_emu"))
    tab_top = int(hl_shape.top + hl_shape.height + gap)
    max_top = MAX_KA_BOTTOM_EMU - ka_height
    return min(tab_top, max_top)


def ka_bottom_emu(slide) -> int | None:
    ka = get_key_activities_shape(slide)
    if ka is None:
        return None
    return int(ka.top + ka.height)


def ka_overlaps_footer(slide, max_bottom_emu: int = MAX_KA_BOTTOM_EMU) -> bool:
    bottom = ka_bottom_emu(slide)
    return bottom is not None and bottom > max_bottom_emu


def ka_overlaps_hl_text(slide, profile: dict) -> bool:
    """True when KA sits above the standard HL-table tab gap."""
    ka = get_key_activities_shape(slide)
    if ka is None:
        return False
    try:
        hl = get_highlights_shape(slide)
    except ValueError:
        return False
    gap = hl_ka_tab_gap_emu(profile.get("canonical_line_height_emu"))
    tab_top = int(hl.top + hl.height + gap)
    return ka.top < tab_top


def _merge_slide_geometry(layout_profile: dict, slide_profile: dict) -> dict:
    """Use row metrics from the slide being fitted (contd templates differ from main)."""
    merged = dict(layout_profile)
    for key in ("r0", "r1", "ref_r2", "ref_pad", "ref_para_count", "ref_hl_height", "ref_hl_top", "ref_hl"):
        if key in slide_profile:
            merged[key] = slide_profile[key]
    return merged


def fit_main_slide_hl_ka(
    slide,
    template_prs: Presentation,
    profile: TemplateProfile,
    layout_profile: dict | None = None,
) -> bool:
    """
    Shrink HL to wrap-aware content height; place KA a fixed tab gap below HL table.
    """
    ka = get_key_activities_shape(slide)
    if ka is None:
        return False
    try:
        hl = get_highlights_shape(slide)
    except ValueError:
        return False

    ref_idx = find_standalone_reference_slide(template_prs, profile)
    if ref_idx is None:
        return False

    ref_slide = template_prs.slides[ref_idx]
    ref_ka = get_key_activities_shape(ref_slide)
    if ref_ka is None:
        return False

    slide_profile = build_layout_profile(slide)
    layout_profile = apply_fixed_story_line_metrics(
        _merge_slide_geometry(dict(layout_profile or slide_profile), slide_profile)
    )

    ka_h = int(ka.height or ref_ka.height)
    gap = hl_ka_tab_gap_emu()
    max_hl_h = int(MAX_KA_BOTTOM_EMU - ka_h - gap - hl.top)

    fit_hl_to_content(hl, layout_profile, max_h=max_hl_h)

    # Re-apply KA position after HL resize (table bottom may have moved).
    ka.left = ref_ka.left
    ka.width = ref_ka.width
    ka.height = ka_h
    ka.top = effective_ka_top(hl, layout_profile, ka_h)

    if ka_overlaps_hl_text(slide, layout_profile):
        logger.warning("KA above HL tab gap after fit — layout may need contd slide")
        return False
    if ka_overlaps_footer(slide):
        logger.warning("KA overlaps footer after fit")
        return False
    return True


def fit_hl_only_on_slide(slide, layout_profile: dict | None = None) -> int:
    """Size Highlights to content only, up to the full HL-only slide budget."""
    try:
        hl = get_highlights_shape(slide)
    except ValueError:
        return 0
    if layout_profile is None:
        layout_profile = build_layout_profile(slide)
    layout_profile = apply_fixed_story_line_metrics(layout_profile)
    max_h = int(MAX_KA_BOTTOM_EMU - layout_profile["ref_hl"].top - MIN_HL_BOTTOM_PAD_EMU)
    height = fit_hl_to_content(hl, layout_profile, max_h=max_h)
    from app.wsr_engine.formatter import top_align_highlights_on_slide

    top_align_highlights_on_slide(slide)
    return height


def ensure_key_activities_on_slide(
    slide,
    template_prs: Presentation,
    profile: TemplateProfile,
) -> object | None:
    """Clone empty KA when missing on any project slide."""
    ka = get_key_activities_shape(slide)
    if ka is not None:
        return ka

    ref_idx = find_standalone_reference_slide(template_prs, profile)
    if ref_idx is None:
        logger.warning("No standalone KA reference slide in template")
        return None
    ref_ka = get_key_activities_shape(template_prs.slides[ref_idx])
    if ref_ka is None:
        return None
    new_el = copy.deepcopy(ref_ka.element)
    slide.shapes._spTree.insert_element_before(new_el, "p:extLst")
    ka = get_key_activities_shape(slide)
    if ka is None:
        return None
    logger.debug("Inserted KA tab on slide")
    return ka


def ensure_key_activities_on_main_slide(
    slide,
    template_prs: Presentation,
    service: ServiceProfile,
    profile: TemplateProfile,
):
    """Clone empty KA when missing; always fit HL+KA geometry on main slides."""
    if service.ka_mode == "embedded":
        return get_key_activities_shape(slide)

    ka = ensure_key_activities_on_slide(slide, template_prs, profile)
    if ka is None:
        return None

    fit_main_slide_hl_ka(slide, template_prs, profile)
    return ka


def finalize_project_hl_ka(
    prs: Presentation,
    main_idx: int,
    contd_indices: list[int],
    template_prs: Presentation,
    service: ServiceProfile,
    profile: TemplateProfile,
    layout_profile: dict | None = None,
    ka_on_main: bool = False,
    ka_contd_only: bool = False,
) -> None:
    """
    Place Key Activities only on the last slide of a project; tighten HL on every slide.

    When overflow continues on (Contd..) slides, earlier slides use HL-only layout
    (full vertical budget). The final slide holds HL + empty KA placeholders.
    """
    from app.wsr_engine.formatter import clear_ka_on_slide, remove_ka_from_slide

    template_slide = template_prs.slides[service.main_slide_index]
    fit_profile = apply_fixed_story_line_metrics(
        dict(layout_profile or build_layout_profile(template_slide))
    )
    fit_profile.setdefault("canonical_para_count", fit_profile["ref_para_count"])

    if service.ka_mode == "embedded":
        for idx in contd_indices:
            fit_hl_only_on_slide(prs.slides[idx], fit_profile)
        return

    if ka_on_main:
        main_slide = prs.slides[main_idx]
        ensure_key_activities_on_slide(main_slide, template_prs, profile)
        fit_main_slide_hl_ka(main_slide, template_prs, profile, layout_profile=fit_profile)
        clear_ka_on_slide(main_slide, template_slide, service)
        return

    if ka_contd_only:
        main_slide = prs.slides[main_idx]
        remove_ka_from_slide(main_slide)
        fit_hl_only_on_slide(main_slide, fit_profile)
        if contd_indices:
            clear_ka_on_slide(prs.slides[contd_indices[-1]], template_slide, service)
        return

    last_idx = contd_indices[-1] if contd_indices else main_idx
    hl_only_indices = [main_idx] + [i for i in contd_indices if i != last_idx]

    for idx in hl_only_indices:
        slide = prs.slides[idx]
        remove_ka_from_slide(slide)
        fit_hl_only_on_slide(slide, fit_profile)

    last_slide = prs.slides[last_idx]
    remove_ka_from_slide(last_slide)
    ensure_key_activities_on_slide(last_slide, template_prs, profile)
    fit_main_slide_hl_ka(last_slide, template_prs, profile, layout_profile=fit_profile)
    clear_ka_on_slide(last_slide, template_slide, service)
