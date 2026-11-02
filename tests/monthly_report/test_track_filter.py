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


def test_keys_for_cost_core_service():
    sections = {
        "COST": _section("COST", "Cost Core Service"),
        "PRC": _section("PRC", "Pricing Core"),
    }
    display = {"COST": "Cost Core Service", "PRC": "Pricing Core"}
    assert keys_for_track_name(
        "Cost core service", sections_by_key=sections, display_names=display
    ) == ["COST"]


def test_supplier_name_matches_both_sup_and_spur():
    sections = {
        "SUP": _section("SUP", "Supplier Core Service"),
        "SPUR": _section("SPUR", "Supplier Core Service"),
    }
    display = {"SUP": "Supplier Core Service", "SPUR": "Supplier Core Service"}
    assert keys_for_track_name(
        "Supplier Core Service", sections_by_key=sections, display_names=display
    ) == ["SUP", "SPUR"]


def test_filter_sections_respects_track_order():
    sections = [
        _section("PRC", "Pricing Core"),
        _section("COST", "Cost Core Service"),
        _section("GSS", "Global Sourcing Solution"),
    ]
    filtered, warnings = filter_sections_by_track_names(
        sections, ["Cost Core Service", "Pricing Core"]
    )
    assert warnings == []
    assert [s.project_key for s in filtered] == ["COST", "PRC"]


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
