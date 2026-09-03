"""Tests for category-header bullet validation against WSR templates."""

from __future__ import annotations

import pytest

from app.constants.ppt_bullets import (
    CategoryBulletSpec,
    is_valid_category_header_bullet,
)
from app.services.ppt_format_extractor import extract_deck
from app.services.ppt_format_reference import load_evaluation_reference, resolve_evaluation_template
from app.services.template_typography import extract_template_typography

GENERIC_TEMPLATE = (
    "templates/G10X H-E-B WSR Haskell Location Pharmacy GSS PAM 11 July 2025- Generic Template.pptx"
)


def test_sustainment_wingdings_category_bullet_spec() -> None:
    spec = CategoryBulletSpec(
        levels=frozenset({7}),
        bullet_chars=frozenset({"\u00d8"}),
        bullet_fonts=frozenset({"Wingdings,Sans-Serif"}),
    )
    assert spec.matches("\u00d8", "Wingdings,Sans-Serif", 7)
    assert not spec.matches("\u2022", "Arial MT", 0)


def test_generic_template_open_circle_category_bullet() -> None:
    spec = CategoryBulletSpec(
        levels=frozenset({1}),
        bullet_chars=frozenset({"o"}),
        bullet_fonts=frozenset({"Courier New"}),
    )
    assert spec.matches("o", "Courier New", 1)
    assert not spec.matches("o", "Arial MT", 1)


def test_missing_spec_skips_category_bullet_validation() -> None:
    assert is_valid_category_header_bullet("\u2022", "Arial MT", 0, spec=None)


@pytest.mark.skipif(not __import__("pathlib").Path(GENERIC_TEMPLATE).is_file(), reason="Generic template missing")
def test_generic_template_extracts_open_circle_category_bullets() -> None:
    typography = extract_template_typography(GENERIC_TEMPLATE)
    assert typography.category_bullet is not None
    assert 1 in typography.category_bullet.levels
    assert typography.category_bullet.matches("o", "Courier New", 1)


@pytest.mark.skipif(not __import__("pathlib").Path(GENERIC_TEMPLATE).is_file(), reason="Generic template missing")
def test_pricing_contd_slide_matches_template_category_bullets() -> None:
    tpl = resolve_evaluation_template(GENERIC_TEMPLATE)
    ref = load_evaluation_reference(tpl, use_rendered_bounds=False)
    deck = extract_deck(
        "output/HEB_Delivery_Status.pptx",
        reference_template=ref.template_path,
        category_bullet_spec=ref.typography.category_bullet,
        label_spec=ref.label_spec,
        use_rendered_bounds=False,
    )
    slide = next(
        s for s in deck["slides"]
        if "Pricing Core" in s.get("title", "") and s.get("is_contd")
    )
    assert slide["highlights"].get("category_bullet_violations") == []
