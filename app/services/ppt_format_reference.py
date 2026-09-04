"""Resolve typography and layout thresholds for template-scoped deck evaluation.

Evaluation ground truth is defined in ``app.constants.evaluation_ground_truth``:
EXPECTED values come from the template; ACTUAL values from the generated deck.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.ppt_format_extractor import extract_deck
from app.services.template_calibration import (
    TemplateLayoutThresholds,
    calibrate_from_deck,
    load_thresholds,
)
from app.services.template_layout_spec import TemplateLayoutSpec, extract_template_layout_spec
from app.services.template_label_spec import TemplateLabelSpec, extract_template_label_spec
from app.services.template_spacing_spec import TemplateSpacingSpec, extract_template_spacing_spec
from app.services.template_typography import TemplateTypographySpec, load_template_typography
from app.services.wsr_template import resolve_wsr_template


@dataclass(frozen=True)
class EvaluationReference:
    template_path: Path
    typography: TemplateTypographySpec
    thresholds: TemplateLayoutThresholds
    spacing: TemplateSpacingSpec | None = None
    layout_spec: TemplateLayoutSpec | None = None
    label_spec: TemplateLabelSpec | None = None


def resolve_evaluation_template(explicit: str | Path | None = None) -> Path:
    """Pick the templates-folder reference deck for format evaluation."""
    return resolve_wsr_template(explicit)


def load_evaluation_reference(
    template_path: str | Path,
    *,
    calibrate_thresholds: bool = True,
    use_rendered_bounds: bool = False,
) -> EvaluationReference:
    """
    Build evaluation reference data from a WSR template in templates/.

    Typography always comes from the template. Layout thresholds and prototype
    HL/KA geometry are calibrated from measured delivery slides in that same
    template when ``calibrate_thresholds`` is True; otherwise the cached default
    threshold JSON is used (legacy fallback only).
    """
    template_path = Path(template_path).resolve()
    if not template_path.is_file():
        raise FileNotFoundError(f"Evaluation template not found: {template_path}")

    label_spec = extract_template_label_spec(template_path)
    typography = load_template_typography(template_path, label_spec=label_spec)
    spacing = extract_template_spacing_spec(template_path)
    layout_spec: TemplateLayoutSpec | None = None
    if calibrate_thresholds:
        template_deck = extract_deck(
            template_path,
            reference_template=template_path,
            category_bullet_spec=typography.category_bullet,
            label_spec=label_spec,
            use_rendered_bounds=use_rendered_bounds,
        )
        thresholds = calibrate_from_deck(template_deck)
        layout_spec = extract_template_layout_spec(template_deck)
    else:
        thresholds = load_thresholds()

    return EvaluationReference(
        template_path=template_path,
        typography=typography,
        thresholds=thresholds,
        spacing=spacing,
        layout_spec=layout_spec,
        label_spec=label_spec,
    )
