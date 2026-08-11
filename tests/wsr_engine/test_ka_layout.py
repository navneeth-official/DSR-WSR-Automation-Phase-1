"""Tests for KA tab insertion on ka_mode=none slides."""

from __future__ import annotations

from pathlib import Path

import pytest
from pptx import Presentation

from app.services.ppt_shape_utils import get_highlights_shape, get_key_activities_shape
from app.services.template_profile import scan_template_profile
from app.wsr_engine.content_parser import load_content, section_display_content
from app.wsr_engine.formatter import discover_section_templates, fill_highlights_on_slide, get_canonical_style_cell
from app.services.ppt_layout_metrics import hl_ka_tab_gap_emu
from app.wsr_engine.ka_layout import (
    effective_ka_top,
    ensure_key_activities_on_main_slide,
    finalize_project_hl_ka,
    ka_overlaps_footer,
    ka_overlaps_hl_text,
)
from app.wsr_engine.overflow_engine import build_layout_profile, plan_overflow, build_overflow_profile
from app.wsr_engine.project_matcher import match_projects
from app.wsr_engine.template_analyzer import analyze_template

HASKELL = (
    Path(__file__).resolve().parents[2]
    / "templates"
    / "G10X H-E-B WSR Haskell Location Pharmacy GSS PAM 01 Aug 2025.pptx"
)
CONTENT = Path(__file__).resolve().parents[2] / "output" / "ppt_content.json"


@pytest.mark.skipif(not HASKELL.is_file(), reason="Haskell sample template missing")
def test_ensure_ka_inserts_tab_on_cost_core():
    prs = Presentation(str(HASKELL))
    profile = scan_template_profile(HASKELL)
    svc = profile.services["Cost Core Service"]
    slide = prs.slides[svc.main_slide_index]
    assert get_key_activities_shape(slide) is None
    ensure_key_activities_on_main_slide(slide, prs, svc, profile)
    assert get_key_activities_shape(slide) is not None


@pytest.mark.skipif(
    not HASKELL.is_file() or not CONTENT.is_file(),
    reason="Haskell template or ppt_content.json missing",
)
def test_ensure_ka_sits_at_fixed_tab_gap_on_dense_supplier_slide():
    prs = Presentation(str(HASKELL))
    profile = scan_template_profile(HASKELL)
    svc = profile.services["Supplier Core Service"]
    slide = prs.slides[svc.main_slide_index]

    content = load_content(CONTENT)
    template = analyze_template(HASKELL)
    supplier = match_projects(template, content.projects, None)["Supplier Core Service"]
    sections = [section_display_content(s) for s in supplier.sections[:3]]
    tmpl = discover_section_templates(get_canonical_style_cell(prs, profile))
    fill_highlights_on_slide(slide, tmpl, sections)
    ensure_key_activities_on_main_slide(slide, prs, svc, profile)

    hl = get_highlights_shape(slide)
    template_slide = prs.slides[svc.main_slide_index]
    layout = build_layout_profile(template_slide)
    layout.setdefault("canonical_para_count", layout["ref_para_count"])
    layout.setdefault(
        "canonical_per_line_emu",
        int(layout["ref_r2"] / max(layout["ref_para_count"] - 2, 1)),
    )
    assert not ka_overlaps_hl_text(slide, layout)
    assert not ka_overlaps_footer(slide)
    gap = hl_ka_tab_gap_emu(layout.get("canonical_line_height_emu"))
    assert ka.top - (hl.top + hl.height) == gap


@pytest.mark.skipif(not HASKELL.is_file(), reason="Haskell sample template missing")
def test_effective_ka_top_ignores_text_bottom():
    """KA placement uses HL table bottom + tab gap only."""
    prs = Presentation(str(HASKELL))
    profile = scan_template_profile(HASKELL)
    svc = profile.services["Supplier Core Service"]
    slide = prs.slides[svc.main_slide_index]
    hl = get_highlights_shape(slide)
    layout = build_layout_profile(slide)
    layout["canonical_line_height_emu"] = 142875
    ka_h = 900000
    expected = hl.top + hl.height + hl_ka_tab_gap_emu(142875)
    assert effective_ka_top(hl, layout, ka_h) == min(expected, 5747107 - ka_h)


@pytest.mark.skipif(
    not HASKELL.is_file() or not CONTENT.is_file(),
    reason="Haskell template or ppt_content.json missing",
)
def test_ka_only_on_last_slide_when_overflow():
    """Cost Core overflow: main slide has no KA; last contd slide has KA."""
    from app.services.ppt_shape_utils import slide_title_text
    from app.wsr_engine.continuation_engine import ensure_continuation_slides
    from app.wsr_engine.overflow_engine import main_slide_capacity

    prs = Presentation(str(HASKELL))
    profile = scan_template_profile(HASKELL)
    svc = profile.services["Cost Core Service"]
    main_idx = svc.main_slide_index
    main_slide = prs.slides[main_idx]
    template_slide = prs.slides[main_idx]

    content = load_content(CONTENT)
    template = analyze_template(HASKELL)
    cost = match_projects(template, content.projects, None)["Cost Core Service"]
    tmpl = discover_section_templates(get_canonical_style_cell(prs, profile))

    layout_profile = build_overflow_profile(prs, template_slide, svc, profile)
    overflow = plan_overflow(cost, layout_profile, main_cap=main_slide_capacity(layout_profile))
    fill_highlights_on_slide(main_slide, tmpl, overflow.main_sections)

    contd_indices: list[int] = []
    if overflow.continuation_chains:
        from app.wsr_engine.models import TitleFormat

        title_format = TitleFormat(prefix="Delivery Status", separator=" - ", contd_marker="(Contd..)")
        contd_indices, _ = ensure_continuation_slides(
            prs,
            prs,
            "Cost Core Service",
            main_idx,
            overflow.continuation_chains,
            svc,
            main_idx,
            title_format,
            tmpl,
        )

    finalize_project_hl_ka(
        prs, main_idx, contd_indices, prs, svc, profile, layout_profile=layout_profile
    )

    assert overflow.continuation_chains, "Cost Core fixture should overflow to contd"
    assert get_key_activities_shape(main_slide) is None
    last_contd = prs.slides[contd_indices[-1]]
    assert get_key_activities_shape(last_contd) is not None
    assert "(contd" in slide_title_text(last_contd).lower()

    hl = get_highlights_shape(last_contd)
    fit_layout = dict(layout_profile)
    fit_layout.setdefault("canonical_para_count", fit_layout["ref_para_count"])
    fit_layout.setdefault(
        "canonical_per_line_emu",
        int(fit_layout["ref_r2"] / max(fit_layout["ref_para_count"] - 2, 1)),
    )
    hl_h_in = hl.height / 914400
    assert hl_h_in < 3.5, f"contd HL should be content-sized, got {hl_h_in:.2f}in"
    assert not ka_overlaps_hl_text(last_contd, fit_layout)
