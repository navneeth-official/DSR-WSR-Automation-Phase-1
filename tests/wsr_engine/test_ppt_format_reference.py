"""Tests for template-scoped PPT format evaluation reference."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.paths import REPO_ROOT
from app.services.ppt_format_extractor import _uds_helpers, extract_deck
from app.services.ppt_format_reference import (
    load_evaluation_reference,
    resolve_evaluation_template,
)
from app.services.wsr_template import list_templates_folder_pptx, resolve_wsr_template

ROOT = REPO_ROOT


def _active_template() -> Path | None:
    templates = list_templates_folder_pptx()
    return templates[0] if templates else None


@pytest.mark.skipif(_active_template() is None, reason="No WSR template in templates/")
def test_resolve_evaluation_template_uses_templates_folder() -> None:
    expected = resolve_wsr_template()
    resolved = resolve_evaluation_template()
    assert resolved.resolve() == expected.resolve()


@pytest.mark.skipif(_active_template() is None, reason="No WSR template in templates/")
def test_load_evaluation_reference_uses_template_typography() -> None:
    template = resolve_wsr_template()
    reference = load_evaluation_reference(template, use_rendered_bounds=False)
    assert reference.template_path.resolve() == template.resolve()
    assert reference.typography.template_file
    assert reference.thresholds.calibrated_slide_count >= 0
    assert reference.layout_spec is not None
    assert reference.layout_spec.hl.width > 0
    assert reference.label_spec is not None
    assert reference.label_spec.template_file


@pytest.mark.skipif(_active_template() is None, reason="No WSR template in templates/")
def test_calibration_derives_container_thresholds_from_template() -> None:
    template = resolve_wsr_template()
    reference = load_evaluation_reference(template, use_rendered_bounds=False)
    thresholds = reference.thresholds
    assert thresholds.template_file
    assert thresholds.hl_waste_above_text_max_in > 0
    assert thresholds.container_underutilization_max_util > 0
    assert any("top waste" in note.lower() for note in thresholds.calibration_notes)


@pytest.mark.skipif(_active_template() is None, reason="No WSR template in templates/")
def test_extract_deck_uses_reference_template_for_layout_helpers() -> None:
    template = resolve_wsr_template()
    _, ref_prs = _uds_helpers(template)
    deck = extract_deck(
        template,
        reference_template=template,
        use_rendered_bounds=False,
    )
    assert deck["slide_count"] >= 0
    assert len(ref_prs.slides) == len(list(ref_prs.slides))


def test_resolve_evaluation_template_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pptx"
    with pytest.raises(FileNotFoundError):
        resolve_evaluation_template(missing)
