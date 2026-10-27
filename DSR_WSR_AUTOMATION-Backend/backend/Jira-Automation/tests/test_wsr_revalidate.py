"""Re-check deck: SharePoint eTag skip, pull + validate, fallbacks and error mapping."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import paths
from app.api.routes import wsr as wsr_routes
from app.services import sharepoint_upload_service as sp
from app.services import wsr_revalidate_service as rv
from app.services import wsr_validation_service as svc

START = date(2026, 10, 26)
END = date(2026, 10, 30)
BODY = {
    "start_date": START.isoformat(),
    "end_date": END.isoformat(),
    "variant": 1,
    "template_id": "tpl1",
}
FILENAME = "WSR_2026-10-26_2026-10-30.pptx"


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.remote: dict[str, Any] = {"eTag": '"etag-1"', "webUrl": "https://sp/x", "id": "item1"}
        self.metadata_error: Exception | None = None
        self.download_error: Exception | None = None
        self.validation_fails = False
        self.downloads: list[str] = []
        self.validations = 0

    def ppt(self) -> Path:
        return paths.wsr_output_paths(START, END).ppt_path

    def write_local_deck(self) -> None:
        self.ppt().write_bytes(b"local")

    def write_report(self) -> None:
        paths.wsr_validation_report_path(START, END).write_text(
            json.dumps(
                {"deck_pass": False, "summary": {"total_findings": 3, "fail": 1, "warn": 2}}
            ),
            encoding="utf-8",
        )
        svc._write_status(START, END, 1, "ready")

    def write_fingerprint(self, etag: str) -> None:
        paths.wsr_validation_fingerprint_path(START, END).write_text(
            json.dumps({"eTag": etag}), encoding="utf-8"
        )


@pytest.fixture()
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    h = Harness(tmp_path)
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(svc, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(rv, "resolve_cloud_provider", lambda: "sharepoint")

    def fake_metadata(filename: str) -> dict[str, Any]:
        if h.metadata_error:
            raise h.metadata_error
        assert filename == FILENAME
        return dict(h.remote)

    def fake_download(filename: str, destination: Path) -> Path:
        if h.download_error:
            raise h.download_error
        h.downloads.append(filename)
        destination.write_bytes(b"remote")
        return destination

    def fake_validation(start: date, end: date, *, variant: int = 1, template_id: str | None = None):
        h.validations += 1
        if h.validation_fails:
            svc._write_error(start, end, variant, RuntimeError("boom"))
            return None
        h.write_report()
        return {"deck_pass": False, "finding_count": 3, "fail": 1, "warn": 2}

    monkeypatch.setattr(rv, "get_sharepoint_item_metadata", fake_metadata)
    monkeypatch.setattr(rv, "download_ppt_from_sharepoint", fake_download)
    monkeypatch.setattr(rv, "run_wsr_validation", fake_validation)
    return h


@pytest.fixture()
def client(harness: Harness) -> TestClient:
    app = FastAPI()
    app.include_router(wsr_routes.router)
    return TestClient(app)


def test_unchanged_skips_download_and_validation(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    harness.write_report()
    harness.write_fingerprint('"etag-1"')

    response = client.post("/api/wsr/revalidate", json=BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unchanged"
    assert body["pulled"] is False
    assert body["findings_count"] == 3
    assert body["fail_count"] == 1
    assert body["warn_count"] == 2
    assert harness.downloads == []
    assert harness.validations == 0


def test_changed_sharepoint_pulls_and_validates(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    harness.write_report()
    harness.write_fingerprint('"old-etag"')

    response = client.post("/api/wsr/revalidate", json=BODY)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "validated"
    assert body["pulled"] is True
    assert body["eTag"] == '"etag-1"'
    assert harness.downloads == [FILENAME]
    assert harness.validations == 1
    assert harness.ppt().read_bytes() == b"remote"

    fingerprint = json.loads(
        paths.wsr_validation_fingerprint_path(START, END).read_text(encoding="utf-8")
    )
    assert fingerprint["eTag"] == '"etag-1"'
    assert fingerprint["filename"] == FILENAME
    assert fingerprint["template_id"] == "tpl1"

    # The stored SharePoint item meta now carries the pulled eTag, too.
    assert sp.load_sharepoint_item_meta(START, END)["eTag"] == '"etag-1"'


def test_force_ignores_matching_etag(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    harness.write_report()
    harness.write_fingerprint('"etag-1"')

    response = client.post("/api/wsr/revalidate", json={**BODY, "force": True})

    assert response.json()["status"] == "validated"
    assert harness.downloads == [FILENAME]
    assert harness.validations == 1


def test_missing_fingerprint_validates_once(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    harness.write_report()

    assert client.post("/api/wsr/revalidate", json=BODY).json()["status"] == "validated"
    # Second call: fingerprint now exists and SharePoint is unchanged.
    assert client.post("/api/wsr/revalidate", json=BODY).json()["status"] == "unchanged"
    assert harness.validations == 1


def test_local_only_validates_without_graph(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    harness.metadata_error = AssertionError("Graph must not be called")

    response = client.post("/api/wsr/revalidate", json={**BODY, "from_sharepoint": False})

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "validated"
    assert body["pulled"] is False
    assert harness.downloads == []
    assert harness.ppt().read_bytes() == b"local"


def test_sharepoint_down_falls_back_to_local_deck(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    harness.metadata_error = RuntimeError("graph down")

    response = client.post("/api/wsr/revalidate", json=BODY)

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "validated"
    assert body["pulled"] is False
    assert "SharePoint was unavailable" in body["message"]
    assert not paths.wsr_validation_fingerprint_path(START, END).exists()


def test_download_failure_keeps_local_deck_and_validates_it(
    harness: Harness, client: TestClient
) -> None:
    harness.write_local_deck()
    harness.download_error = RuntimeError("download broke")

    response = client.post("/api/wsr/revalidate", json=BODY)

    body = response.json()
    assert response.status_code == 200
    assert body["pulled"] is False
    assert "could not be downloaded" in body["message"]
    assert harness.ppt().read_bytes() == b"local"
    assert not paths.wsr_validation_fingerprint_path(START, END).exists()


def test_deck_missing_everywhere_is_404(harness: Harness, client: TestClient) -> None:
    harness.metadata_error = FileNotFoundError("not in sharepoint")

    response = client.post("/api/wsr/revalidate", json=BODY)

    assert response.status_code == 404


def test_missing_local_deck_without_sharepoint_is_404(
    harness: Harness, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rv, "resolve_cloud_provider", lambda: None)

    response = client.post("/api/wsr/revalidate", json=BODY)

    assert response.status_code == 404


def test_template_unresolved_is_404(
    harness: Harness, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.write_local_deck()
    monkeypatch.setattr(rv, "list_week_variants", lambda *_args: [])

    response = client.post("/api/wsr/revalidate", json={**BODY, "template_id": None})

    assert response.status_code == 404
    assert "template" in response.json()["detail"].lower()


def test_validation_failure_is_502(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    harness.validation_fails = True

    response = client.post("/api/wsr/revalidate", json=BODY)

    assert response.status_code == 502
    assert "boom" in response.json()["detail"]


def test_running_validation_is_409(harness: Harness, client: TestClient) -> None:
    harness.write_local_deck()
    svc.begin_validation(START, END)

    response = client.post("/api/wsr/revalidate", json=BODY)

    assert response.status_code == 409


def test_fingerprint_recorded_from_stored_upload_meta(harness: Harness) -> None:
    harness.write_local_deck()
    sp.save_sharepoint_item_meta(START, END, {"webUrl": "https://sp/x", "eTag": '"up-1"', "id": "i"})

    assert rv.record_validation_fingerprint_from_sharepoint(START, END, template_id="tpl1") is True
    assert rv.load_validation_fingerprint(START, END)["eTag"] == '"up-1"'


def test_fingerprint_not_recorded_without_sharepoint(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rv, "resolve_cloud_provider", lambda: None)
    assert rv.record_validation_fingerprint_from_sharepoint(START, END, template_id="tpl1") is False


# ── SharePoint helpers ────────────────────────────────────────────────────────

class _Response:
    def __init__(self, status: int, content: bytes = b"", payload: dict | None = None) -> None:
        self.status_code = status
        self.content = content
        self.text = content.decode("utf-8", "ignore")
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def test_download_replaces_file_only_for_valid_pptx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sp, "get_sharepoint_access_token", lambda: "token")
    monkeypatch.setattr(sp, "_upload_folder", lambda: "Shared Documents/WSR")
    monkeypatch.setattr(
        sp, "_build_sharepoint_item_url", lambda folder, filename: f"https://graph/{folder}/{filename}:"
    )
    destination = tmp_path / FILENAME
    destination.write_bytes(b"local")

    monkeypatch.setattr(sp.requests, "get", lambda *_a, **_k: _Response(200, b"<html>login</html>"))
    with pytest.raises(RuntimeError):
        sp.download_ppt_from_sharepoint(FILENAME, destination)
    assert destination.read_bytes() == b"local"

    monkeypatch.setattr(sp.requests, "get", lambda *_a, **_k: _Response(200, b"PK\x03\x04data"))
    sp.download_ppt_from_sharepoint(FILENAME, destination)
    assert destination.read_bytes() == b"PK\x03\x04data"
    assert not (tmp_path / f"{FILENAME}.download").exists()


def test_metadata_normalises_item_and_maps_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sp, "get_sharepoint_access_token", lambda: "token")
    monkeypatch.setattr(sp, "_upload_folder", lambda: "Shared Documents/WSR")
    monkeypatch.setattr(sp, "_build_sharepoint_item_url", lambda folder, filename: "https://graph/x:")

    payload = {
        "webUrl": "https://sp/x",
        "id": "item1",
        "cTag": "ctag",
        "name": FILENAME,
        "parentReference": {"driveId": "drive1"},
    }
    monkeypatch.setattr(sp.requests, "get", lambda *_a, **_k: _Response(200, payload=payload))
    item = sp.get_sharepoint_item_metadata(FILENAME)
    assert item["eTag"] == "ctag"  # falls back to cTag
    assert item["driveId"] == "drive1"

    monkeypatch.setattr(sp.requests, "get", lambda *_a, **_k: _Response(404, b"nope"))
    with pytest.raises(FileNotFoundError):
        sp.get_sharepoint_item_metadata(FILENAME)


def test_per_variant_sharepoint_meta_is_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    sp.save_sharepoint_item_meta(START, END, {"webUrl": "https://sp/v1"}, variant=1)
    sp.save_sharepoint_item_meta(START, END, {"webUrl": "https://sp/v2"}, variant=2)

    assert sp.load_sharepoint_web_url(START, END) == "https://sp/v1"
    assert sp.load_sharepoint_web_url(START, END, variant=2) == "https://sp/v2"
    assert sp.load_sharepoint_web_url(START, END, variant=3) is None
    # Variant 1 keeps the legacy week-level file name.
    assert (tmp_path / "WSR_2026-10-26_2026-10-30_sharepoint.json").is_file()
    assert (tmp_path / "WSR_2026-10-26_2026-10-30_v2_sharepoint.json").is_file()
