"""Index rebuild must list whatever projects are in the deck, not only HEB keywords."""

from __future__ import annotations

from types import SimpleNamespace

from app.wsr_engine.index_layout import IndexLayout, IndexSlot
from app.wsr_engine.index_updater import _collect_rebuild_entries
from app.wsr_engine.models import ProjectMap


def test_collect_rebuild_entries_uses_deck_projects_not_template_slots() -> None:
    projects = [
        ProjectMap(project_name="Cost Core Service", main_slide_index=2),
        ProjectMap(project_name="Supplier Core", main_slide_index=5),
        ProjectMap(project_name="Supplier Portal", main_slide_index=7),
        ProjectMap(project_name="Pharmacy Digital", main_slide_index=8),
        ProjectMap(project_name="RXD", main_slide_index=9),
    ]
    # Template still only "knows" Cost Core as a delivery slot — new keys must still appear.
    layout = IndexLayout(
        slots=[
            IndexSlot(
                row=0,
                col=0,
                needles=("cost core",),
                search_title="Cost Core Service",
                is_delivery=True,
            ),
            IndexSlot(
                row=1,
                col=1,
                needles=("matters of attention",),
                search_title="Matters of Attention",
                is_delivery=False,
            ),
        ]
    )
    content_labels = {
        "Cost Core Service": "Cost Core Service",
        "Supplier Core": "Supplier Core",
        "Supplier Portal": "Supplier Portal",
        "Pharmacy Digital": "Pharmacy Digital",
        "RXD": "RXD",
    }

    # Avoid needing a real Presentation for static-slot lookup: stub finder via monkeypatch.
    import app.wsr_engine.index_updater as idx

    original = idx._find_static_slide_index

    def _fake_static(_prs, title_fragment: str):
        if "matters" in title_fragment.lower():
            return 11
        return None

    idx._find_static_slide_index = _fake_static  # type: ignore[assignment]
    try:
        entries = _collect_rebuild_entries(
            SimpleNamespace(),  # prs unused for delivery rows
            projects,
            layout,
            content_labels,
        )
    finally:
        idx._find_static_slide_index = original  # type: ignore[assignment]

    labels = [label for _, label in entries]
    assert labels[:5] == [
        "Cost Core Service",
        "Supplier Core",
        "Supplier Portal",
        "Pharmacy Digital",
        "RXD",
    ]
    assert labels[-1] == "Matters of Attention"
    assert [idx for idx, _ in entries[:5]] == [2, 5, 7, 8, 9]
