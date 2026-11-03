"""Index rows must follow each delivery track, not one repeated template title."""

from app.wsr_engine.index_updater import _match_project_for_index, delivery_index_entries
from app.wsr_engine.models import ProjectMap


def test_delivery_index_entries_use_each_track_title_and_slide():
    projects = [
        ProjectMap(project_name="Cost Core Service", main_slide_index=2),
        ProjectMap(project_name="Patronage Travel", main_slide_index=4),
        ProjectMap(project_name="RXD", main_slide_index=6),
    ]
    labels = {
        "Cost Core Service": "Cost Core Service",
        "Patronage Travel": "Patronage Travel",
        "RXD": "RXD",
    }
    assert delivery_index_entries(projects, labels) == [
        (2, "Cost Core Service"),
        (4, "Patronage Travel"),
        (6, "RXD"),
    ]


def test_core_service_template_slot_does_not_match_cost():
    projects = [
        ProjectMap(project_name="Cost Core Service", main_slide_index=2),
        ProjectMap(project_name="Patronage Travel", main_slide_index=4),
        ProjectMap(project_name="RXD", main_slide_index=6),
    ]
    assert _match_project_for_index(projects, "Cost Core Service").project_name == "Cost Core Service"
    assert _match_project_for_index(projects, "Supplier Core Service") is None
    assert _match_project_for_index(projects, "Pricing Core Service") is None
    assert _match_project_for_index(projects, "Location Core Service") is None
