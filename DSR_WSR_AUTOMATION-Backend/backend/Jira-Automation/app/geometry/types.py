"""Value types for geometry-driven layout inspection and correction."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RepairMode(str, Enum):
    """Single coherent repair strategy for one slide."""

    TIGHTEN_AND_POSITION = "tighten_and_position"
    ENSURE_CLEARANCE = "ensure_clearance"
    EXPAND_AND_REFLOW = "expand_and_reflow"
    COMPACT_VERTICAL = "compact_vertical"
    SHRINK_KA = "shrink_ka"
    SHRINK_HL = "shrink_hl"
    FIX_FOOTER_OVERFLOW = "fix_footer_overflow"
    NONE = "none"


@dataclass(frozen=True)
class GeometryViolation:
    rule_id: str
    severity: str
    slide_index: int | None
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GeometryViolation:
        return cls(
            rule_id=str(raw.get("rule_id") or ""),
            severity=str(raw.get("severity") or "minor"),
            slide_index=int(raw["slide_index"]) if raw.get("slide_index") is not None else None,
            title=str(raw.get("title") or ""),
            message=str(raw.get("message") or ""),
            details=dict(raw.get("details") or {}),
        )


@dataclass
class SlideGeometryReport:
    slide_index: int
    title: str
    layout_type: str
    metrics: dict[str, Any] = field(default_factory=dict)
    violations: list[GeometryViolation] = field(default_factory=list)
    manual_review_required: bool = False
    manual_review_reasons: list[str] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return bool(self.violations)

    @property
    def has_critical(self) -> bool:
        return any(v.severity == "critical" for v in self.violations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "title": self.title,
            "layout_type": self.layout_type,
            "metrics": self.metrics,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "message": v.message,
                    "details": v.details,
                }
                for v in self.violations
            ],
            "violation_count": len(self.violations),
            "manual_review_required": self.manual_review_required,
            "manual_review_reasons": self.manual_review_reasons,
        }


@dataclass
class GeometryReport:
    """Deterministic geometry inspection result for a deck."""

    ppt_path: str
    slides: list[SlideGeometryReport] = field(default_factory=list)
    violation_count: int = 0
    critical_count: int = 0

    @property
    def passes(self) -> bool:
        return self.violation_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ppt_path": self.ppt_path,
            "passes": self.passes,
            "violation_count": self.violation_count,
            "critical_count": self.critical_count,
            "slides": [s.to_dict() for s in self.slides],
        }


@dataclass(frozen=True)
class SlideRepairPlan:
    """One coherent geometry correction for a slide (no conflicting micro-actions)."""

    slide_index: int
    mode: RepairMode
    layout_mode: str = "normal"
    expand_for_wrap: bool = False
    reason: str = ""
    triggered_by: tuple[str, ...] = ()

    @property
    def applies_change(self) -> bool:
        return self.mode != RepairMode.NONE


@dataclass
class SlideGeometryDelta:
    """Before/after geometry proof for one corrected slide."""

    slide_index: int
    changed: bool
    plan_mode: str
    reason: str
    metrics_before: dict[str, Any] = field(default_factory=dict)
    metrics_after: dict[str, Any] = field(default_factory=dict)
    metric_deltas: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "changed": self.changed,
            "plan_mode": self.plan_mode,
            "reason": self.reason,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "metric_deltas": self.metric_deltas,
        }


@dataclass
class GeometryCorrectionResult:
    modified: bool
    ppt_path: str
    actions_applied: list[str] = field(default_factory=list)
    slides_modified: list[int] = field(default_factory=list)
    slides_unchanged: list[int] = field(default_factory=list)
    slide_deltas: list[SlideGeometryDelta] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "modified": self.modified,
            "ppt_path": self.ppt_path,
            "actions_applied": self.actions_applied,
            "slides_modified": self.slides_modified,
            "slides_unchanged": self.slides_unchanged,
            "slide_deltas": [d.to_dict() for d in self.slide_deltas],
            "failures": self.failures,
            "message": self.message,
        }
