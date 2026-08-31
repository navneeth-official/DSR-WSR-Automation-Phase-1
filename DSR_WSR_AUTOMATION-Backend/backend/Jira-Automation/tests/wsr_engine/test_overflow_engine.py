"""Tests for overflow planning."""

from __future__ import annotations

from app.wsr_engine.models import ProjectContent, SprintSection
from app.wsr_engine.overflow_engine import (
    HL_KA_SAME_SLIDE_MAX,
    UNIVERSAL_HL_ONLY_CAP,
    get_hl_budgets,
    hl_only_slide_capacity,
    plan_overflow,
)


def _make_profile(*, with_ka: bool = False):
    profile = {
        "ref_hl": None,
        "ref_ka": object() if with_ka else None,
        "r0": 100000,
        "r1": 100000,
        "ref_r2": 2000000,
        "ref_pad": 50000,
        "ref_para_count": 10,
        "ref_hl_height": 2500000,
        "ref_hl_top": 1000000,
    }
    if with_ka:
        profile["expanded_hl_height"] = 1800000
    return profile


def test_overflow_keeps_sprint_sections_whole():
    sections = [
        SprintSection("S1", "Jan 01 – Jan 14", "Ended", ["a"], [], []),
        SprintSection("S2", "Jan 15 – Jan 28", "Ended", ["b", "c"], [], []),
        SprintSection("S3", "Feb 01 – Feb 14", "In-progress", [], [], ["d"]),
    ]
    project = ProjectContent(title="Test", sections=sections)
    plan = plan_overflow(project, _make_profile(), main_cap=8, hl_only_cap=8)

    all_sprint_names = set()
    for s in plan.main_sections:
        all_sprint_names.add(s["sprint_bold"])
    for chain in plan.continuation_chains:
        for s in chain:
            all_sprint_names.add(s["sprint_bold"])

    assert len(all_sprint_names) == 3


def test_no_overflow_when_fits():
    sections = [SprintSection("S1", "Jan 01 – Jan 14", "Ended", ["a"], [], [])]
    project = ProjectContent(title="Test", sections=sections)
    plan = plan_overflow(project, _make_profile(), main_cap=20)
    assert plan.continuation_chains == []


def test_oversized_section_does_not_infinite_loop():
    """A single sprint section larger than cap must still produce continuation chains."""
    sections = [
        SprintSection(
            "S1",
            "Jan 01 – Jan 14",
            "Ended",
            [f"story-{i}" for i in range(10)],
            [],
            [],
        ),
        SprintSection("S2", "Jan 15 – Jan 28", "Ended", ["b"], [], []),
    ]
    project = ProjectContent(title="Test", sections=sections)
    plan = plan_overflow(project, _make_profile(), main_cap=4, hl_only_cap=4)

    assert plan.continuation_chains
    all_sprints = {s["sprint_bold"] for s in plan.main_sections}
    for chain in plan.continuation_chains:
        all_sprints.update(s["sprint_bold"] for s in chain)
    assert len(all_sprints) == 2


def test_single_slide_uses_hl_ka_cap_when_content_fits():
    """Content that fits HL+KA budget stays on one slide even when HL-only cap is larger."""
    sections = [SprintSection("S1", "Jan 01 – Jan 14", "Ended", ["a", "b"], [], [])]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    budgets = get_hl_budgets(profile)
    cap = budgets["with_ka_cap"]
    plan = plan_overflow(project, profile)
    assert plan.continuation_chains == []
    assert len(plan.main_sections) == 1


def test_hl_only_cap_is_universal():
    assert hl_only_slide_capacity(_make_profile()) == UNIVERSAL_HL_ONLY_CAP
    assert UNIVERSAL_HL_ONLY_CAP == 26


def test_overflow_packs_main_with_hl_only_cap_when_ka_would_not_fit():
    """When HL exceeds the same-slide budget but is below 26, KA moves to contd."""
    sections = [
        SprintSection("S1", "Jan 01 – Jan 14", "Ended", ["a"], [], []),
        SprintSection("S2", "Jan 15 – Jan 28", "Ended", ["b"], [], []),
    ]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    plan = plan_overflow(project, profile)
    assert plan.ka_contd_only or plan.continuation_chains or plan.ka_on_main


def test_ka_on_main_when_under_20_lines_and_fits():
    sections = [SprintSection("S1", "Jan 01 – Jan 14", "Ended", ["a"], [], [])]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    plan = plan_overflow(project, profile)
    assert plan.ka_on_main or plan.ka_contd_only
    assert not plan.continuation_chains


def test_ka_contd_when_under_20_lines_but_physical_overflow():
    """Dense content under 20 lines still moves KA to contd when HL+KA cannot fit."""
    sections = [
        SprintSection(
            "S1",
            "Jan 01 – Jan 14",
            "Ended",
            [f"story-{i}" for i in range(8)],
            [f"rel-{i}" for i in range(4)],
            [f"prog-{i}" for i in range(3)],
        ),
    ]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    profile["ref_hl_top"] = 1_000_000
    profile["r0"] = 200_000
    profile["r1"] = 100_000
    from app.services.ppt_layout_metrics import hl_ka_fits_on_main_slide
    from app.wsr_engine.overflow_engine import _total_display_lines
    from app.wsr_engine.content_parser import section_display_content

    total = _total_display_lines([section_display_content(s) for s in sections])
    plan = plan_overflow(project, profile)
    if not hl_ka_fits_on_main_slide(profile, total):
        assert plan.ka_contd_only
        assert not plan.ka_on_main


def test_ka_contd_only_in_middle_band():
    """20 < total < 26 keeps HL on main and flags KA for a contd slide."""
    sections = [
        SprintSection(
            "S1",
            "Jan 01 – Jan 14",
            "Ended",
            [f"story-{i}" for i in range(4)],
            [],
            [],
        ),
        SprintSection(
            "S2",
            "Jan 15 – Jan 28",
            "Ended",
            [f"story-{i}" for i in range(4)],
            [],
            [],
        ),
        SprintSection(
            "S3",
            "Feb 01 – Feb 14",
            "In-progress",
            [f"story-{i}" for i in range(3)],
            [],
            [],
        ),
    ]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    plan = plan_overflow(project, profile)
    from app.wsr_engine.overflow_engine import _total_display_lines
    from app.wsr_engine.content_parser import section_display_content

    total = _total_display_lines([section_display_content(s) for s in sections])
    if HL_KA_SAME_SLIDE_MAX < total < UNIVERSAL_HL_ONLY_CAP:
        assert plan.ka_contd_only
        assert len(plan.main_sections) == 3
        assert plan.continuation_chains == []


def test_hl_overflow_when_at_or_above_26_lines():
    sections = [
        SprintSection(
            "S1",
            "Jan 01 – Jan 14",
            "Ended",
            [f"story-{i}" for i in range(13)],
            [],
            [],
        ),
        SprintSection("S2", "Jan 15 – Jan 28", "Ended", ["b"], [], []),
    ]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    plan = plan_overflow(project, profile)
    assert not plan.ka_contd_only
    assert plan.continuation_chains
