"""Shared fixtures: an in-memory SharePoint and an isolated local work directory."""

from __future__ import annotations

from pathlib import Path

import pytest
from fake_sharepoint import DATA, DECKS, TEMPLATES, FakeSharePoint

from app import paths
from app.services import pptx_editor_service
from app.services import sharepoint_storage as storage
from app.services import wsr_template_upload_service as template_service
from app.services import wsr_variant_service as variant_service


@pytest.fixture()
def fake_sp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeSharePoint:
    """Fake SharePoint + a fresh temp work dir wired into every module that cached paths."""
    fake = FakeSharePoint()
    work = tmp_path / "work"
    work.mkdir()

    monkeypatch.setattr(paths, "OUTPUT_DIR", work)
    monkeypatch.setattr(paths, "WORK_DIR", work)
    monkeypatch.setattr(paths, "WSR_TEMPLATES_DIR", work / "wsr_templates")
    monkeypatch.setattr(paths, "WSR_TEMPLATE_DRAFT_PPT", work / "WSR_TEMPLATE_DRAFT.pptx")
    monkeypatch.setattr(paths, "WSR_TEMPLATE_DRAFT_META", work / "WSR_TEMPLATE_DRAFT.json")
    monkeypatch.setattr(template_service, "WSR_TEMPLATES_DIR", work / "wsr_templates")
    monkeypatch.setattr(template_service, "WSR_TEMPLATE_DRAFT_PPT", work / "WSR_TEMPLATE_DRAFT.pptx")
    monkeypatch.setattr(template_service, "WSR_TEMPLATE_DRAFT_META", work / "WSR_TEMPLATE_DRAFT.json")
    monkeypatch.setattr(variant_service, "OUTPUT_DIR", work)
    monkeypatch.setattr(pptx_editor_service, "OUTPUT_DIR", work)

    for name in (
        "storage_configured",
        "require_storage",
        "list_folder",
        "get_item",
        "upload_file",
        "download_file",
        "delete_file",
    ):
        monkeypatch.setattr(storage, name, getattr(fake, name))
    monkeypatch.setattr(storage, "decks_folder", lambda: DECKS)
    monkeypatch.setattr(storage, "templates_folder", lambda: TEMPLATES)
    monkeypatch.setattr(storage, "data_folder", lambda: DATA)
    return fake
