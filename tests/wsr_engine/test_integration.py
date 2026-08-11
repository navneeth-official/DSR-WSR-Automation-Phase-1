"""End-to-end integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pptx import Presentation

from app.wsr_engine.main import WsrEngine

TEMPLATE = Path(__file__).resolve().parents[2] / "templates" / "wsr_template.pptx"
G10X = Path(__file__).resolve().parents[2] / "templates" / "G10X H-E-B WSR Sustainment 05 June 2026 .pptx"


def _sample_content() -> dict:
    return {
        "report_start_date": "2026-04-16",
        "report_end_date": "2026-06-15",
        "slides": [
            {
                "title": "Cost Core Service",
                "project_key": "COST",
                "sections": [
                    {
                        "sprint_name": "Q3.01 FY26 Atlas",
                        "sprint_dates": "Jun 04 – Jun 17",
                        "sprint_status": "Ended",
                        "completed": ["Validate buyer funding validation logic"],
                        "released": [],
                        "inprogress": [],
                    }
                ],
            },
            {
                "title": "Location Core Service",
                "project_key": "LOC",
                "project_name": "Location",
                "sections": [
                    {
                        "sprint_name": "Houston - 250",
                        "sprint_dates": "May 30 – Jun 12",
                        "sprint_status": "inprogress",
                        "completed": [],
                        "released": [],
                        "inprogress": ["Add region filters"],
                    }
                ],
            },
        ],
    }


@pytest.mark.parametrize("template", [TEMPLATE, G10X])
def test_end_to_end_build(tmp_path: Path, template: Path):
    if not template.is_file():
        pytest.skip(f"template missing: {template}")

    content_path = tmp_path / "content.json"
    content_path.write_text(json.dumps(_sample_content()), encoding="utf-8")
    output_path = tmp_path / "output.pptx"

    report = WsrEngine().run(
        template_path=template,
        content_path=content_path,
        output_path=output_path,
    )

    assert output_path.is_file()
    assert report.matched_projects >= 1
    assert report.errors == []
    assert len(Presentation(output_path).slides) > 0
