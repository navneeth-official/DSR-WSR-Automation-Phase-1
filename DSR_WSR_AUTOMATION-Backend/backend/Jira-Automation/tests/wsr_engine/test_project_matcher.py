"""Tests for fuzzy project matching."""

from __future__ import annotations

from app.wsr_engine.models import ProjectContent, ProjectMap, TemplateModel
from app.wsr_engine.project_matcher import match_projects


def _template(*names: str) -> TemplateModel:
    return TemplateModel(
        template_path="test.pptx",
        projects=[
            ProjectMap(project_name=n, main_slide_index=i)
            for i, n in enumerate(names)
        ],
    )


def test_pricing_matches_pricing_core_service():
    tmpl = _template("Pricing Core Service", "Cost Core Service")
    content = [ProjectContent(title="Pricing Core Service", project_name="Pricing")]
    matched = match_projects(tmpl, content, {})
    assert "Pricing Core Service" in matched


def test_supplier_qa_matches_supplier_core():
    tmpl = _template("Supplier Core Service")
    content = [ProjectContent(title="Supplier Core Service", project_name="Supplier QA")]
    matched = match_projects(tmpl, content, {"Supplier QA": "Supplier Core Service"})
    assert "Supplier Core Service" in matched


def test_location_matches_location_core():
    tmpl = _template("Location Core Service")
    content = [ProjectContent(title="Location Core Service", project_name="Location")]
    matched = match_projects(tmpl, content, {})
    assert "Location Core Service" in matched
