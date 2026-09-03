"""Compare generated slide geometry against the template prototype."""

from __future__ import annotations

from typing import Any

from app.services.template_layout_spec import TemplateLayoutSpec


def _deviation(
    *,
    rule_id: str,
    severity: str,
    slide_index: int | None,
    title: str,
    element: str,
    property_name: str,
    expected: float,
    actual: float,
    tolerance: float,
) -> dict[str, Any]:
    delta = round(actual - expected, 4)
    direction = "above" if delta > 0 else "below"
    return {
        "rule_id": rule_id,
        "severity": severity,
        "slide_index": slide_index,
        "title": title,
        "target": element,
        "message": (
            f"{element} {property_name} deviates from template prototype "
            f"({actual:.3f} in vs expected {expected:.3f} in, "
            f"{abs(delta):.3f} in {direction} tolerance {tolerance:.3f} in). "
            f"Align with the template layout."
        ),
        "expected_in": expected,
        "actual_in": actual,
        "delta_in": delta,
        "tolerance_in": tolerance,
    }


def detect_template_layout_deviations(
    slide: dict[str, Any],
    *,
    layout_spec: TemplateLayoutSpec | None,
) -> list[dict[str, Any]]:
    """Flag HL/KA placement and sizing that diverges from the template prototype."""
    if layout_spec is None or slide.get("is_contd"):
        return []

    violations: list[dict[str, Any]] = []
    idx = slide.get("slide_index")
    title = slide.get("title", "")
    pos_tol = layout_spec.position_tolerance_in
    size_tol = layout_spec.size_tolerance_in

    hl = slide.get("highlights")
    if hl:
        hl_pos = hl.get("position_in") or {}
        expected = layout_spec.hl
        for prop, rule_id in (
            ("top", "LAY-HL-TOP"),
            ("left", "LAY-HL-LEFT"),
            ("width", "LAY-HL-WIDTH"),
        ):
            actual = hl_pos.get(prop)
            if actual is None:
                continue
            expected_val = getattr(expected, prop)
            tol = pos_tol if prop in ("top", "left") else size_tol
            if abs(float(actual) - expected_val) > tol:
                violations.append(
                    _deviation(
                        rule_id=rule_id,
                        severity="major",
                        slide_index=idx,
                        title=title,
                        element="Highlights tab",
                        property_name=prop,
                        expected=expected_val,
                        actual=float(actual),
                        tolerance=tol,
                    )
                )

    ka = slide.get("key_activities")
    if ka and layout_spec.ka:
        ka_pos = ka.get("position_in") or {}
        expected_ka = layout_spec.ka
        for prop, rule_id in (
            ("left", "LAY-KA-LEFT"),
            ("width", "LAY-KA-WIDTH"),
        ):
            actual = ka_pos.get(prop)
            if actual is None:
                continue
            expected_val = getattr(expected_ka, prop)
            tol = pos_tol if prop in ("top", "left") else size_tol
            if abs(float(actual) - expected_val) > tol:
                violations.append(
                    _deviation(
                        rule_id=rule_id,
                        severity="major",
                        slide_index=idx,
                        title=title,
                        element="Key Activities tab",
                        property_name=prop,
                        expected=expected_val,
                        actual=float(actual),
                        tolerance=tol,
                    )
                )

    return violations
