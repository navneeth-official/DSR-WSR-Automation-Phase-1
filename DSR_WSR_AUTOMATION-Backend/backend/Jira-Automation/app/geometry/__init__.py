"""Geometry-driven layout inspection and correction."""

from app.geometry.confidence import (
    GatedQualitativeIssue,
    categories_for_correction,
    gate_qualitative_issue,
    requires_manual_review,
)
from app.geometry.corrector import GeometryCorrector
from app.geometry.inspector import GeometryInspector
from app.geometry.planner import (
    QUALITATIVE_TO_RULES,
    plan_slide_repair,
    qualitative_compatible_with_geometry,
)
from app.geometry.types import (
    GeometryCorrectionResult,
    GeometryReport,
    GeometryViolation,
    RepairMode,
    SlideGeometryReport,
    SlideRepairPlan,
)

__all__ = [
    "GeometryCorrector",
    "GeometryCorrectionResult",
    "GeometryInspector",
    "GeometryReport",
    "GeometryViolation",
    "GatedQualitativeIssue",
    "QUALITATIVE_TO_RULES",
    "RepairMode",
    "SlideGeometryReport",
    "SlideRepairPlan",
    "categories_for_correction",
    "gate_qualitative_issue",
    "plan_slide_repair",
    "qualitative_compatible_with_geometry",
    "requires_manual_review",
]
