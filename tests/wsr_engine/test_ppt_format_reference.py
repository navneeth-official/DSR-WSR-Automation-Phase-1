"""Tests for template-scoped PPT format evaluation reference."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.paths import GENERIC_WSR_TEMPLATE, REPO_ROOT
from app.services.ppt_format_extractor import _uds_helpers, extract_deck
from app.services.ppt_format_reference import (
    load_evaluation_reference,
    resolve_evaluation_template,
)

ROOT = REPO_ROOT


@pytest.mark.skipif(not GENERIC_WSR_TEMPLATE.is_file(), reason="Generic WSR template missing")
def test_resolve_evaluation_template_prefers_generic_template() -> None:
    resolved = resolve_evaluation_template()
    assert resolved.resolve() == GENERIC_WSR_TEMPLATE.resolve()


@pytest.mark.skipif(not GENERIC_WSR_TEMPLATE.is_file(), reason="Generic WSR template missing")
def test_load_evaluation_reference_uses_template_typography() -> None:
    reference = load_evaluation_reference(GENERIC_WSR_TEMPLATE, use_rendered_bounds=False)
    assert reference.template_path.resolve() == GENERIC_WSR_TEMPLATE.resolve()
    assert reference.typography.template_file
    assert reference.thresholds.calibrated_slide_count >= 0
    assert reference.layout_spec is not None
    assert reference.layout_spec.hl.width > 0
    assert reference.label_spec is not None
    assert reference.label_spec.template_file


@pytest.mark.skipif(not GENERIC_WSR_TEMPLATE.is_file(), reason="Generic WSR template missing")
def test_calibration_derives_container_thresholds_from_template() -> None:
    reference = load_evaluation_reference(GENERIC_WSR_TEMPLATE, use_rendered_bounds=False)
    thresholds = reference.thresholds
    assert thresholds.template_file
    assert thresholds.hl_waste_above_text_max_in > 0
    assert thresholds.container_underutilization_max_util > 0
    assert any("top waste" in note.lower() for note in thresholds.calibration_notes)


@pytest.mark.skipif(not GENERIC_WSR_TEMPLATE.is_file(), reason="Generic WSR template missing")
def test_extract_deck_uses_reference_template_for_layout_helpers() -> None:
    _, ref_prs = _uds_helpers(GENERIC_WSR_TEMPLATE)
    deck = extract_deck(
        GENERIC_WSR_TEMPLATE,
        reference_template=GENERIC_WSR_TEMPLATE,
        use_rendered_bounds=False,
    )
    assert deck["slide_count"] >= 0
    assert len(ref_prs.slides) == len(list(ref_prs.slides))


def test_resolve_evaluation_template_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pptx"
    with pytest.raises(FileNotFoundError):
        resolve_evaluation_template(missing)
