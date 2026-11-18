from monthly_report.deck import ProjectSection
from monthly_report.index_slide import IndexProject, index_entries_for_track_names
from monthly_report.metrics import SprintMetrics
from datetime import date

from monthly_report.track_filter import (
    filter_sections_by_track_names,
    keys_for_track_name,
    parse_track_names,
)


def _section(key: str, title: str) -> ProjectSection:
    sprint = SprintMetrics(
        sprint_name="S1",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 15),
        status="Ended",
        db_status="Ended",
        total=1,
        completed=1,
        in_review=0,
        in_progress=0,
        spill_over=None,
        other=0,
    )
    return ProjectSection(project_key=key, title=title, sprints=[sprint])


def test_parse_track_names_splits_and_dedupes():
    assert parse_track_names(["Cost Core Service", "Pricing Core, GSS"], "") == [
        "Cost Core Service",
        "Pricing Core",
        "GSS",
    ]
    assert parse_track_names(None, "Cost Core Service, Cost Core Service") == ["Cost Core Service"]


def test_keys_match_db_project_key_or_name():
    sections = {
        "COST": _section("COST", "Cost Core Service"),
        "SM": _section("SM", "Supplier Core"),
    }
    assert keys_for_track_name("COST", sections_by_key=sections) == ["COST"]
    assert keys_for_track_name("Cost Core Service", sections_by_key=sections) == ["COST"]
    assert keys_for_track_name("Supplier Core", sections_by_key=sections) == ["SM"]
    assert keys_for_track_name("SM", sections_by_key=sections) == ["SM"]


def test_same_display_name_matches_multiple_keys():
    sections = {
        "SUP": _section("SUP", "Supplier Core Service"),
        "SPUR": _section("SPUR", "Supplier Core Service"),
    }
    assert keys_for_track_name("Supplier Core Service", sections_by_key=sections) == ["SUP", "SPUR"]


def test_unknown_track_not_pulled_from_static_config():
    sections = {"COST": _section("COST", "Cost Core Service")}
    assert keys_for_track_name("PRC", sections_by_key=sections) == []


def test_filter_sections_respects_track_order():
    sections = [
        _section("PRC", "Pricing"),
        _section("COST", "Cost Core Service"),
        _section("GSS", "Global Sourcing Solution"),
    ]
    filtered, warnings = filter_sections_by_track_names(
        sections, ["Cost Core Service", "Pricing"]
    )
    assert warnings == []
    assert [s.project_key for s in filtered] == ["COST", "PRC"]


def test_filter_warns_when_track_has_no_data_in_period():
    sections = [_section("COST", "Cost Core Service")]
    filtered, warnings = filter_sections_by_track_names(sections, ["COST", "PRC"])
    assert [s.project_key for s in filtered] == ["COST"]
    assert any("PRC" in w for w in warnings)


def test_index_single_label_when_multiple_tracks():
    projects = [
        IndexProject("Cost Core Service", 2),
        IndexProject("Pricing Core", 5),
    ]
    labels = {"Cost Core Service": "Cost Core Service", "Pricing Core": "Pricing Core"}
    assert index_entries_for_track_names(
        ["Cost Core Service", "Pricing Core"], projects, labels
    ) == [(2, "Cost Core Service")]
    assert index_entries_for_track_names(["Cost Core Service"], projects[:1], labels) == [
        (2, "Cost Core Service"),
    ]
