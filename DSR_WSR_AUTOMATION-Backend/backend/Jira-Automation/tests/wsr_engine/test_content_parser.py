"""Tests for content parser."""

from __future__ import annotations

import json
from pathlib import Path

from app.wsr_engine.content_parser import load_content


def test_load_content_from_json(tmp_path: Path):
    data = {
        "report_start_date": "2026-04-16",
        "report_end_date": "2026-06-15",
        "slides": [
            {
                "title": "Cost Core Service",
                "project_key": "COST",
                "sections": [
                    {
                        "sprint_name": "Q3.01",
                        "sprint_dates": "Jun 04 – Jun 17",
                        "sprint_status": "Ended",
                        "completed": ["Story A"],
                        "released": [],
                        "inprogress": [],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "content.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    content = load_content(path)
    assert len(content.projects) == 1
    assert content.projects[0].sections[0].completed == ["Story A"]
