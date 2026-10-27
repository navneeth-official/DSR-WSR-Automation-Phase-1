"""Validation status, annotation listing and image serving for generated WSR decks."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import paths
from app.api.routes import wsr as wsr_routes
from app.services import wsr_validation_service as svc

START = date(2026, 10, 26)
END = date(2026, 10, 30)
PARAMS = {"start_date": START.isoformat(), "end_date": END.isoformat()}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(paths, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(wsr_routes, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(svc, "OUTPUT_DIR", tmp_path)
    app = FastAPI()
    app.include_router(wsr_routes.router)
    return TestClient(app)


def _write_report(tmp_path: Path) -> Path:
    report = paths.wsr_validation_report_path(START, END)
    report.write_text(
        json.dumps(
            {
                "source_file": "C:/secret/dir/WSR.pptx",
                "slide_summaries": [{"slide_index": 4, "slide_number": 5, "pass": False}],
                "findings": [
                    {
                        "slide_index": 4,
                        "rule_id": "HL-WASTE-01",
                        "severity": "fail",
                        "annotation_label": "Empty space here",
                        "image": "C:/secret/dir/slide_4_hl-waste-01.png",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return report


def test_status_not_started_then_pending_then_ready(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/api/wsr/validation-status", params=PARAMS).json()["status"] == "not_started"

    svc.begin_validation(START, END)
    assert client.get("/api/wsr/validation-status", params=PARAMS).json()["status"] == "pending"
    assert client.get("/api/wsr/validation-report", params=PARAMS).status_code == 404

    _write_report(tmp_path)
    svc._write_status(START, END, 1, "ready")
    body = client.get("/api/wsr/validation-status", params=PARAMS).json()
    assert body["status"] == "ready"
    assert body["has_annotations"] is False


def test_status_error_reports_message(client: TestClient) -> None:
    svc._write_error(START, END, 1, RuntimeError("boom"))
    body = client.get("/api/wsr/validation-status", params=PARAMS).json()
    assert body["status"] == "error"
    assert "boom" in body["message"]


def test_begin_validation_clears_stale_results(client: TestClient, tmp_path: Path) -> None:
    _write_report(tmp_path)
    image_dir = paths.wsr_validation_dir(START, END)
    image_dir.mkdir()
    (image_dir / "slide_4_hl-waste-01.png").write_bytes(b"png")

    svc.begin_validation(START, END)

    assert not paths.wsr_validation_report_path(START, END).exists()
    assert not image_dir.exists()


def test_report_strips_server_paths(client: TestClient, tmp_path: Path) -> None:
    _write_report(tmp_path)
    body = client.get("/api/wsr/validation-report", params=PARAMS).json()
    assert body["source_file"] == "WSR.pptx"
    assert body["findings"][0]["image"] == "slide_4_hl-waste-01.png"


def test_annotations_list_and_image(client: TestClient, tmp_path: Path) -> None:
    _write_report(tmp_path)
    image_dir = paths.wsr_validation_dir(START, END)
    image_dir.mkdir()
    (image_dir / "slide_4_hl-waste-01.png").write_bytes(b"png")
    (image_dir / "notes.txt").write_text("ignored")

    items = client.get("/api/wsr/annotations", params=PARAMS).json()
    assert len(items) == 1
    assert items[0]["slide_number"] == 5
    assert items[0]["rule_id"] == "HL-WASTE-01"
    assert items[0]["severity"] == "fail"
    assert items[0]["label"] == "Empty space here"

    image = client.get(items[0]["image_url"])
    assert image.status_code == 200
    assert image.content == b"png"


@pytest.mark.parametrize("name", ["../secret.png", "slide_1_x/../../a.png", "report.json", "slide_x.png"])
def test_annotation_image_rejects_bad_names(client: TestClient, name: str) -> None:
    response = client.get("/api/wsr/annotation-image", params={**PARAMS, "filename": name})
    assert response.status_code in (400, 404)


def test_annotation_image_missing_is_404(client: TestClient) -> None:
    response = client.get(
        "/api/wsr/annotation-image", params={**PARAMS, "filename": "slide_9_geo-02.png"}
    )
    assert response.status_code == 404


def test_run_validation_records_error_instead_of_raising(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "WSR_2026-10-26_2026-10-30.pptx").write_bytes(b"not a real pptx")
    monkeypatch.setattr(svc, "RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(svc, "_template_id_for_variant", lambda *a, **k: "tpl")
    monkeypatch.setattr(svc, "resolve_template_path", lambda _id: tmp_path / "tpl.pptx")

    assert svc.run_wsr_validation(START, END, variant=1) is None

    status = svc.get_validation_status(START, END)
    assert status["status"] == "error"
    assert paths.wsr_validation_error_path(START, END).is_file()
