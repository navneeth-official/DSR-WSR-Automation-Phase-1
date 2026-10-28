"""WSR templates and decks are stored only in SharePoint (local dir = disposable cache)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import paths
from app.services import sharepoint_storage as storage
from app.services import sharepoint_upload_service as sp
from app.services import wsr_deck_store as deck_store
from app.services import wsr_service
from app.services import wsr_template_upload_service as templates
from app.services import wsr_variant_service as variants
from app.services.work_cache import purge_stale_work_cache
from fake_sharepoint import DATA, DECKS, TEMPLATES, FakeSharePoint, make_pptx

START = date(2026, 10, 26)
END = date(2026, 10, 30)
DECK = "WSR_2026-10-26_2026-10-30.pptx"
CONTENT = {"report_start_date": "2026-10-26", "report_end_date": "2026-10-30", "slides": [], "meta": {}}


def _wipe_cache() -> None:
    shutil.rmtree(paths.OUTPUT_DIR)
    paths.OUTPUT_DIR.mkdir()


# ── Work dir is outside the repo ──────────────────────────────────────────────

def test_default_work_dir_is_outside_the_backend_folder() -> None:
    work = paths.WORK_DIR.resolve()
    assert paths.REPO_ROOT not in work.parents and work != paths.REPO_ROOT
    assert paths.OUTPUT_DIR == paths.WORK_DIR


def test_work_dir_inside_repo_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WSR_WORK_DIR", str(paths.REPO_ROOT / "output"))
    with pytest.raises(RuntimeError, match="outside the backend folder"):
        paths._resolve_work_dir()


# ── Templates → Shared Documents/WSR Template ─────────────────────────────────

@pytest.fixture()
def no_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(templates, "export_template_slide_previews", lambda **_k: [])


def test_uploaded_template_keeps_its_own_file_name_in_sharepoint(
    fake_sp: FakeSharePoint, no_render: None, tmp_path: Path
) -> None:
    content = make_pptx(tmp_path / "t.pptx")

    result = templates.save_uploaded_template(content=content, original_filename="My WSR.pptx")

    assert result["id"] == "My_WSR"
    assert fake_sp.names(TEMPLATES) == ["My WSR.json", "My WSR.pptx"]
    assert fake_sp.files[(TEMPLATES, "My WSR.pptx")] == content
    meta = json.loads(fake_sp.files[(TEMPLATES, "My WSR.json")])
    assert meta["original_filename"] == "My WSR.pptx"


def test_same_file_name_uploaded_twice_gets_a_counter_not_an_overwrite(
    fake_sp: FakeSharePoint, no_render: None, tmp_path: Path
) -> None:
    first = make_pptx(tmp_path / "a.pptx", slides=1)
    second = make_pptx(tmp_path / "b.pptx", slides=3)

    one = templates.save_uploaded_template(content=first, original_filename="WSR Template.pptx")
    two = templates.save_uploaded_template(content=second, original_filename="WSR Template.pptx")

    assert fake_sp.names(TEMPLATES) == [
        "WSR Template (2).json",
        "WSR Template (2).pptx",
        "WSR Template.json",
        "WSR Template.pptx",
    ]
    assert fake_sp.files[(TEMPLATES, "WSR Template.pptx")] == first
    assert fake_sp.files[(TEMPLATES, "WSR Template (2).pptx")] == second
    assert one["id"] != two["id"]
    assert {t["id"] for t in templates.list_saved_templates()} == {one["id"], two["id"]}


def test_file_name_is_cleaned_for_sharepoint() -> None:
    assert templates.safe_remote_stem("G10X H-E-B WSR 05 June 2026 .pptx") == "G10X H-E-B WSR 05 June 2026"
    assert templates.safe_remote_stem("a:b?c#d.pptx") == "a_b_c_d"
    assert templates.safe_remote_stem("C:\\docs\\Deck v1.2.pptx") == "Deck v1.2"
    assert templates.template_id_from_stem("Deck v1.2 (2)") == "Deck_v1_2_2"


def test_templates_saved_with_old_random_names_still_work(
    fake_sp: FakeSharePoint, no_render: None, tmp_path: Path
) -> None:
    content = make_pptx(tmp_path / "t.pptx")
    fake_sp.put(TEMPLATES, "a1b2c3d4e5f6.pptx", content)
    fake_sp.put(TEMPLATES, "a1b2c3d4e5f6.json", b'{"original_filename": "Old.pptx"}')

    assert [t["id"] for t in templates.list_saved_templates()] == ["a1b2c3d4e5f6"]
    assert templates.get_template_info("a1b2c3d4e5f6")["original_filename"] == "Old.pptx"


def test_template_survives_local_cache_wipe(
    fake_sp: FakeSharePoint, no_render: None, tmp_path: Path
) -> None:
    content = make_pptx(tmp_path / "t.pptx")
    result = templates.save_uploaded_template(content=content, original_filename="a.pptx")
    template_id = result["id"]
    assert template_id == "a"

    _wipe_cache()

    listed = templates.list_saved_templates()
    assert [t["id"] for t in listed] == [template_id]
    assert listed[0]["original_filename"] == "a.pptx"

    _wipe_cache()
    resolved = templates.resolve_template_path(template_id)
    assert resolved.is_file() and resolved.read_bytes() == content


def test_unknown_template_is_not_found(fake_sp: FakeSharePoint) -> None:
    with pytest.raises(FileNotFoundError):
        templates.resolve_template_path("nope123")
    with pytest.raises(FileNotFoundError):
        templates.resolve_template_path("../escape")


def test_failed_template_upload_leaves_nothing_behind(
    fake_sp: FakeSharePoint, no_render: None, tmp_path: Path
) -> None:
    fake_sp.fail_uploads = True
    content = make_pptx(tmp_path / "t.pptx")

    with pytest.raises(storage.StorageError):
        templates.save_uploaded_template(content=content, original_filename="a.pptx")

    assert fake_sp.files == {}
    assert list((paths.WSR_TEMPLATES_DIR).glob("*")) == []


def test_staged_draft_is_published_only_on_save(
    fake_sp: FakeSharePoint, no_render: None, tmp_path: Path
) -> None:
    content = make_pptx(tmp_path / "t.pptx")
    templates.stage_template_upload(content=content, original_filename="draft.pptx")
    assert fake_sp.files == {}  # staging is local-only

    info = templates.save_draft_template()

    assert fake_sp.names(TEMPLATES) == ["draft.json", "draft.pptx"]
    assert info["id"] == "draft"
    assert not paths.WSR_TEMPLATE_DRAFT_PPT.exists()


def test_templates_require_sharepoint(fake_sp: FakeSharePoint, no_render: None, tmp_path: Path) -> None:
    fake_sp.configured = False
    with pytest.raises(storage.StorageNotConfiguredError):
        templates.save_uploaded_template(
            content=make_pptx(tmp_path / "t.pptx"), original_filename="a.pptx"
        )
    with pytest.raises(storage.StorageNotConfiguredError):
        templates.list_saved_templates()


# ── Decks → Shared Documents/WSR (+ _data sidecars) ──────────────────────────

def _generate_local_deck(variant: int = 1) -> Path:
    out = paths.wsr_output_paths(START, END, variant=variant)
    make_pptx(out.ppt_path, slides=3)
    out.json_path.write_text(json.dumps(CONTENT), encoding="utf-8")
    out.preview_path.write_text("preview", encoding="utf-8")
    return out.ppt_path


def test_publish_deck_uploads_deck_and_sidecars_and_manifest(fake_sp: FakeSharePoint) -> None:
    ppt = _generate_local_deck()

    item = deck_store.publish_deck(START, END, 1)
    variants.register_generated_variant(
        START, END, variant=1, template_id="tpl1", ppt_path=ppt, slide_count=3
    )

    assert fake_sp.names(DECKS) == [DECK]
    assert fake_sp.names(DATA) == [
        "WSR_2026-10-26_2026-10-30.json",
        "WSR_2026-10-26_2026-10-30_manifest.json",
        "WSR_2026-10-26_2026-10-30_preview.txt",
    ]
    assert deck_store.cloud_fields(item)["sharepoint_web_url"].endswith(DECK)


def test_week_listing_and_load_work_after_cache_wipe(fake_sp: FakeSharePoint) -> None:
    ppt = _generate_local_deck()
    deck_store.publish_deck(START, END, 1)
    variants.register_generated_variant(
        START, END, variant=1, template_id="tpl1", ppt_path=ppt, slide_count=3
    )
    _wipe_cache()

    weeks = wsr_service.list_generated_wsr_weeks()

    assert len(weeks) == 1
    week = weeks[0]
    assert week["filename"] == DECK
    assert week["template_id"] == "tpl1"  # manifest restored from SharePoint
    assert week["slide_count"] == 3
    assert week["cloud_provider"] == "sharepoint"
    assert week["cloud_web_url"].endswith(DECK)

    _wipe_cache()
    assert deck_store.ensure_local_deck(START, END, 1).read_bytes() == fake_sp.files[(DECKS, DECK)]
    assert paths.wsr_output_paths(START, END).ppt_path.is_file()


def test_load_week_restores_deck_and_sidecars(
    fake_sp: FakeSharePoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    ppt = _generate_local_deck()
    deck_store.publish_deck(START, END, 1)
    variants.register_generated_variant(START, END, variant=1, template_id="tpl1", ppt_path=ppt)
    _wipe_cache()
    monkeypatch.setattr(wsr_service, "export_wsr_slide_previews", lambda **_k: [])

    result = wsr_service.load_wsr_week(START, END, variant=1)

    assert result["filename"] == DECK
    assert result["preview"] == "preview"
    assert result["sharepoint_web_url"].endswith(DECK)
    assert result["template_id"] == "tpl1"


def test_missing_deck_is_file_not_found(fake_sp: FakeSharePoint) -> None:
    with pytest.raises(FileNotFoundError):
        deck_store.ensure_local_deck(START, END, 1)
    with pytest.raises(FileNotFoundError):
        wsr_service.load_wsr_week(START, END, variant=1)


def test_deleted_sharepoint_deck_is_dropped_from_manifest(fake_sp: FakeSharePoint) -> None:
    ppt = _generate_local_deck()
    deck_store.publish_deck(START, END, 1)
    variants.register_generated_variant(START, END, variant=1, template_id="tpl1", ppt_path=ppt)
    assert variants.check_wsr_generation(START, END, "tpl1")["can_generate"] is False

    fake_sp.delete_file(DECKS, DECK)

    assert variants.check_wsr_generation(START, END, "tpl1")["can_generate"] is True
    assert wsr_service.list_generated_wsr_weeks() == []


def test_manually_uploaded_deck_is_discovered(fake_sp: FakeSharePoint, tmp_path: Path) -> None:
    fake_sp.put(DECKS, "WSR_2026-10-26_2026-10-30_v2.pptx", make_pptx(tmp_path / "x.pptx"))

    found = variants.list_week_variants(START, END)

    assert [v["variant"] for v in found] == [2]


def test_generate_requires_sharepoint(fake_sp: FakeSharePoint) -> None:
    fake_sp.configured = False
    with pytest.raises(storage.StorageNotConfiguredError):
        wsr_service.generate_wsr_deck(None, start_date=START, end_date=END, template_id="tpl1")  # type: ignore[arg-type]


def test_editor_publish_replaces_deck_in_sharepoint(fake_sp: FakeSharePoint) -> None:
    ppt = _generate_local_deck()
    deck_store.publish_deck(START, END, 1)
    ppt.write_bytes(ppt.read_bytes() + b"edited")

    deck_store.publish_deck_file(START, END, 1)

    assert fake_sp.files[(DECKS, DECK)].endswith(b"edited")


# ── API: SharePoint missing -> clear 503 ──────────────────────────────────────

def test_api_returns_503_when_sharepoint_not_configured(fake_sp: FakeSharePoint) -> None:
    from app.main import app

    fake_sp.configured = False
    response = TestClient(app).get("/api/wsr/weeks")

    assert response.status_code == 503
    assert "SharePoint" in response.json()["detail"]


# ── Validation artefacts → _data/<stem>_validation ────────────────────────────

def test_validation_artifacts_round_trip_through_sharepoint(fake_sp: FakeSharePoint) -> None:
    from app.services import validation_upload_service as vus

    report = paths.wsr_validation_report_path(START, END)
    report.write_text(json.dumps({"deck_pass": True}), encoding="utf-8")
    image_dir = paths.wsr_validation_dir(START, END)
    image_dir.mkdir()
    (image_dir / "slide_3_hl-waste-01.png").write_bytes(b"png3")
    (image_dir / "slide_4_hl-waste-02.png").write_bytes(b"png4")
    folder = f"{DATA}/WSR_2026-10-26_2026-10-30_validation"
    fake_sp.put(folder, "slide_9_old-rule.png", b"stale")

    vus.try_upload_validation_artifacts(START, END)

    assert fake_sp.names(folder) == [
        "WSR_2026-10-26_2026-10-30_validation_report.json",
        "slide_3_hl-waste-01.png",
        "slide_4_hl-waste-02.png",
    ]  # stale image from a previous run was removed

    _wipe_cache()
    assert vus.restore_validation_report(START, END) is True
    assert json.loads(report.read_text(encoding="utf-8")) == {"deck_pass": True}
    assert sorted(p.name for p in image_dir.iterdir()) == [
        "slide_3_hl-waste-01.png",
        "slide_4_hl-waste-02.png",
    ]
    assert vus.restore_validation_image(START, END, "../evil.png") is None


# ── Work-dir housekeeping ─────────────────────────────────────────────────────

def test_purge_stale_work_cache_removes_only_old_files(tmp_path: Path) -> None:
    old = tmp_path / "sub" / "old.pptx"
    new = tmp_path / "new.pptx"
    old.parent.mkdir()
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    past = time.time() - 48 * 3600
    os.utime(old, (past, past))

    deleted = purge_stale_work_cache(tmp_path, max_age_hours=24)

    assert deleted == 1
    assert not old.exists() and not old.parent.exists()
    assert new.exists()
    assert purge_stale_work_cache(tmp_path, max_age_hours=0) == 0


# ── SharePoint transport (Graph calls mocked) ─────────────────────────────────

class _Resp:
    def __init__(self, status: int, payload: dict | None = None, content: bytes = b"", headers=None) -> None:
        self.status_code = status
        self._payload = payload or {}
        self.content = content
        self.text = content.decode("utf-8", "ignore")
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload


@pytest.fixture()
def graph(monkeypatch: pytest.MonkeyPatch):
    """Real storage functions with `requests.request` replaced by a scripted fake."""
    settings = storage.get_settings()
    for key, value in {
        "azure_client_id": "cid",
        "azure_client_secret": "secret",
        "azure_tenant_id": "tenant",
        "sharepoint_site_id": "site1",
        "sharepoint_drive_id": "",
    }.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(storage, "_get_token", lambda **_k: "token")
    monkeypatch.setattr(storage.time, "sleep", lambda *_a: None)
    storage.invalidate_listing()

    class Graph:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []
            self.responses: list[_Resp] = []

        def __call__(self, method, url, **kwargs):
            self.calls.append((method, url))
            return self.responses.pop(0)

    g = Graph()
    monkeypatch.setattr(storage.requests, "request", g)
    return g


def test_list_folder_pages_skips_subfolders_and_caches(graph) -> None:
    graph.responses = [
        _Resp(200, {"value": [{"name": "a.pptx", "size": 1}, {"name": "_data", "folder": {}}],
                    "@odata.nextLink": "https://graph/next"}),
        _Resp(200, {"value": [{"name": "b.pptx", "size": 2}]}),
    ]

    items = storage.list_folder("Shared Documents/WSR")

    assert [i["name"] for i in items] == ["a.pptx", "b.pptx"]
    assert graph.calls[0][1].startswith(
        "https://graph.microsoft.com/v1.0/sites/site1/drive/root:/Shared Documents/WSR:/children"
    )
    assert storage.list_folder("Shared Documents/WSR") == items  # served from cache
    assert len(graph.calls) == 2


def test_missing_folder_lists_as_empty(graph) -> None:
    graph.responses = [_Resp(404)]
    assert storage.list_folder("Shared Documents/WSR Template", use_cache=False) == []


def test_upload_puts_to_item_path_and_invalidates_listing(graph, tmp_path: Path) -> None:
    graph.responses = [_Resp(200, {"value": []}), _Resp(201, {"name": "x.json", "webUrl": "https://sp/x.json"}),
                       _Resp(200, {"value": [{"name": "x.json"}]})]
    assert storage.list_folder("Shared Documents/WSR Template") == []
    local = tmp_path / "x.json"
    local.write_text("{}", encoding="utf-8")

    item = storage.upload_file(local, "Shared Documents/WSR Template")

    assert item["webUrl"] == "https://sp/x.json"
    method, url = graph.calls[1]
    assert method == "PUT"
    assert url.endswith("root:/Shared Documents/WSR Template/x.json:/content")
    assert [i["name"] for i in storage.list_folder("Shared Documents/WSR Template")] == ["x.json"]


def test_failed_upload_raises_storage_error(graph, tmp_path: Path) -> None:
    graph.responses = [_Resp(403, content=b"denied")]
    local = tmp_path / "x.json"
    local.write_text("{}", encoding="utf-8")
    with pytest.raises(storage.StorageError, match="403"):
        storage.upload_file(local, "Shared Documents/WSR")


def test_transient_errors_are_retried(graph, tmp_path: Path) -> None:
    graph.responses = [_Resp(503), _Resp(200, {"name": "a.pptx", "size": 5})]
    item = storage.get_item("Shared Documents/WSR", "a.pptx")
    assert item["name"] == "a.pptx"
    assert len(graph.calls) == 2


def test_download_404_is_none_and_html_is_rejected(graph, tmp_path: Path) -> None:
    dest = tmp_path / "a.pptx"
    graph.responses = [_Resp(404)]
    assert storage.download_file("Shared Documents/WSR", "a.pptx", dest) is None
    assert not dest.exists()

    graph.responses = [_Resp(200, content=b"<html>login</html>")]
    with pytest.raises(storage.StorageError, match="not a valid .pptx"):
        storage.download_file("Shared Documents/WSR", "a.pptx", dest)
    assert not dest.exists()

    graph.responses = [_Resp(200, content=b"PK\x03\x04", headers={"Last-Modified": "Wed, 21 Oct 2026 07:28:00 GMT"})]
    storage.download_file("Shared Documents/WSR", "a.pptx", dest)
    assert dest.read_bytes() == b"PK\x03\x04"
    assert abs(dest.stat().st_mtime - 1792567680) < 5
    assert not (tmp_path / "a.pptx.download").exists()


def test_unconfigured_storage_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = storage.get_settings()
    monkeypatch.setattr(settings, "sharepoint_site_id", "")
    with pytest.raises(storage.StorageNotConfiguredError, match="SHAREPOINT_SITE_ID"):
        storage.list_folder("Shared Documents/WSR")


def test_folder_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = storage.get_settings()
    monkeypatch.setattr(settings, "sharepoint_upload_folder", "Shared Documents/WSR")
    monkeypatch.setattr(settings, "sharepoint_template_folder", "")
    monkeypatch.setattr(settings, "sharepoint_data_folder", "")
    assert storage.templates_folder() == "Shared Documents/WSR Template"
    assert storage.data_folder() == "Shared Documents/WSR/_data"
    monkeypatch.setattr(settings, "sharepoint_data_folder", "Shared Documents/WSR Data")
    assert storage.data_folder() == "Shared Documents/WSR Data"
    assert sp._build_sharepoint_children_url("Shared Documents/WSR").endswith(
        "root:/Shared Documents/WSR:/children"
    )


# ── One-time migration script ─────────────────────────────────────────────────

def _load_migration_script():
    script = paths.REPO_ROOT / "scripts" / "migrate_output_to_sharepoint.py"
    spec = importlib.util.spec_from_file_location("migrate_output_to_sharepoint", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _legacy_output(root: Path) -> Path:
    src = root / "legacy_output"
    (src / "wsr_templates").mkdir(parents=True)
    (src / "wsr_templates" / "abc123.pptx").write_bytes(make_pptx(root / "tpl.pptx"))
    (src / "wsr_templates" / "abc123.json").write_text('{"original_filename": "T.pptx"}', encoding="utf-8")
    make_pptx(src / DECK)
    (src / "WSR_2026-10-26_2026-10-30.json").write_text("{}", encoding="utf-8")
    (src / "WSR_2026-10-26_2026-10-30_preview.txt").write_text("p", encoding="utf-8")
    (src / "WSR_2026-10-26_2026-10-30_validation_report.json").write_text("{}", encoding="utf-8")
    (src / "WSR_2026-10-26_2026-10-30_validation").mkdir()
    (src / "WSR_2026-10-26_2026-10-30_validation" / "slide_3_hl-waste-01.png").write_bytes(b"png")
    (src / "WSR_2026-10-26_2026-10-30_manifest.json").write_text(
        json.dumps({"variants": [{"variant": 1, "template_id": "abc123", "filename": DECK}]}),
        encoding="utf-8",
    )
    (src / "WSR_2026-10-26_2026-10-30_editor.json").write_text("{}", encoding="utf-8")  # not migrated
    (src / "ppt_content.json").write_text("{}", encoding="utf-8")  # not migrated
    return src


def test_migration_plan_maps_files_to_sharepoint_folders(fake_sp: FakeSharePoint, tmp_path: Path) -> None:
    migrate = _load_migration_script()
    src = _legacy_output(tmp_path)

    plan = migrate.plan_migration(src, work_dir=tmp_path / "scratch")

    targets = sorted((u.folder, u.remote_name) for u in plan)
    vdir = f"{DATA}/WSR_2026-10-26_2026-10-30_validation"
    assert targets == sorted(
        [
            (TEMPLATES, "T.pptx"),
            (TEMPLATES, "T.json"),
            (DECKS, DECK),
            (DATA, "WSR_2026-10-26_2026-10-30.json"),
            (DATA, "WSR_2026-10-26_2026-10-30_preview.txt"),
            (DATA, "WSR_2026-10-26_2026-10-30_manifest.json"),
            (vdir, "WSR_2026-10-26_2026-10-30_validation_report.json"),
            (vdir, "slide_3_hl-waste-01.png"),
        ]
    )
    manifest = next(u for u in plan if u.kind == "manifest")
    data = json.loads(manifest.local.read_text(encoding="utf-8"))
    assert data["variants"][0]["filename"] == DECK
    assert data["variants"][0]["slide_count"] == 2
    assert data["variants"][0]["template_id"] == "T"  # old random id -> name-based id


def test_migration_uploads_and_is_idempotent(
    fake_sp: FakeSharePoint, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    migrate = _load_migration_script()
    src = _legacy_output(tmp_path)
    monkeypatch.setattr(sys, "argv", ["migrate", "--source", str(src)])

    assert migrate.main() == 0
    first = dict(fake_sp.files)
    assert (TEMPLATES, "T.pptx") in first and (DECKS, DECK) in first
    uploads_after_first = len(fake_sp.upload_log)

    assert migrate.main() == 0  # re-run only refreshes the manifest
    assert len(fake_sp.upload_log) == uploads_after_first + 1
    assert "skip" in capsys.readouterr().out

    # After migration the app can use the data with an empty local cache.
    _wipe_cache()
    assert [w["filename"] for w in wsr_service.list_generated_wsr_weeks()] == [DECK]
    assert [t["id"] for t in templates.list_saved_templates()] == ["T"]
    assert fake_sp.names(TEMPLATES) == ["T.json", "T.pptx"]  # re-run did not create "T (2)"
