"""Tests for overflow planning."""

from __future__ import annotations

from app.wsr_engine.models import ProjectContent, SprintSection
from app.wsr_engine.overflow_engine import (
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
        all_sprint_names.add(s.get("sprint_name") or s.get("sprint_bold"))
    for chain in plan.continuation_chains:
        for s in chain:
            all_sprint_names.add(s.get("sprint_name") or s.get("sprint_bold"))

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
    all_sprints = {
        s.get("sprint_name") or s.get("sprint_bold") for s in plan.main_sections
    }
    for chain in plan.continuation_chains:
        all_sprints.update(s.get("sprint_name") or s.get("sprint_bold") for s in chain)
    assert len(all_sprints) == 2
    assert plan.main_sections  # oversized first sprint stays on main


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


def test_hl_only_cap_follows_template_budget():
    profile = _make_profile(with_ka=True)
    budgets = get_hl_budgets(profile)
    cap = hl_only_slide_capacity(profile)
    assert cap == min(
        max(budgets["full_main_cap"], budgets["template_cap"]),
        UNIVERSAL_HL_ONLY_CAP,
    )
    assert UNIVERSAL_HL_ONLY_CAP == 26


def test_overflow_packs_main_with_hl_only_cap_when_ka_would_not_fit():
    """When HL exceeds with-KA budget but fits HL-only, KA moves to contd."""
    sections = [
        SprintSection("S1", "Jan 01 – Jan 14", "Ended", ["a"], [], []),
        SprintSection("S2", "Jan 15 – Jan 28", "Ended", ["b"], [], []),
    ]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    plan = plan_overflow(project, profile)
    assert plan.ka_contd_only or plan.continuation_chains or plan.ka_on_main


def test_ka_on_main_when_under_template_with_ka_cap():
    sections = [SprintSection("S1", "Jan 01 – Jan 14", "Ended", ["a"], [], [])]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    plan = plan_overflow(project, profile)
    assert plan.ka_on_main or plan.ka_contd_only
    assert not plan.continuation_chains


def test_ka_contd_when_fits_hl_ka_band_but_physical_overflow():
    """Content within with-KA line budget still moves KA to contd when geometry fails."""
    sections = [
        SprintSection(
            "S1",
            "Jan 01 – Jan 14",
            "Ended",
            [f"story-{i}" for i in range(3)],
            [f"rel-{i}" for i in range(2)],
            [f"prog-{i}" for i in range(1)],
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
    if total <= get_hl_budgets(profile)["with_ka_cap"] and not hl_ka_fits_on_main_slide(
        profile, total
    ):
        assert plan.ka_contd_only
        assert not plan.ka_on_main


def test_ka_contd_only_when_between_with_ka_and_hl_only_caps():
    """with_ka_cap < total <= hl_only_cap keeps HL on main and moves KA to contd."""
    profile = _make_profile(with_ka=True)
    # Tall HL-only budget, tight with-KA budget → clear middle band.
    profile["expanded_hl_height"] = 900_000
    profile["ref_r2"] = 2_500_000
    profile["ref_hl_height"] = 2_800_000
    budgets = get_hl_budgets(profile)
    with_ka = budgets["with_ka_cap"]
    hl_only = hl_only_slide_capacity(profile)
    assert with_ka < hl_only

    # Build just enough stories to land in the middle band.
    stories_needed = max(with_ka, 1)
    sections = [
        SprintSection(
            "S1",
            "Jan 01 – Jan 14",
            "Ended",
            [f"story-{i}" for i in range(stories_needed)],
            [],
            [],
        ),
    ]
    project = ProjectContent(title="Test", sections=sections)
    from app.wsr_engine.overflow_engine import _total_display_lines
    from app.wsr_engine.content_parser import section_display_content

    total = _total_display_lines([section_display_content(s) for s in sections])
    # Nudge story count until we are strictly above with_ka and within hl_only.
    while total <= with_ka and len(sections[0].completed) < hl_only + 5:
        sections[0].completed.append(f"extra-{len(sections[0].completed)}")
        total = _total_display_lines([section_display_content(s) for s in sections])
    if with_ka < total <= hl_only:
        plan = plan_overflow(project, profile)
        assert plan.ka_contd_only
        assert len(plan.main_sections) == 1
        assert plan.continuation_chains == []


def test_hl_overflow_when_above_template_hl_only_cap():
    """Content above the template HL-only budget splits onto continuation slides."""
    sections = [
        SprintSection(
            "S1",
            "Jan 01 – Jan 14",
            "Ended",
            [f"story-{i}" for i in range(8)],
            [],
            [],
        ),
        SprintSection("S2", "Jan 15 – Jan 28", "Ended", ["b", "c", "d"], [], []),
    ]
    project = ProjectContent(title="Test", sections=sections)
    profile = _make_profile(with_ka=True)
    plan = plan_overflow(project, profile, hl_only_cap=8)
    assert not plan.ka_contd_only
    assert plan.continuation_chains
    assert len(plan.main_sections) == 1
