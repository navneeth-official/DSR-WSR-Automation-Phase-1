"""Parse raw vision model JSON into typed results."""

from __future__ import annotations

import json
import re
from typing import Any

from app.vision.exceptions import MalformedVisionResponseError
from app.vision.types import (
    LayoutIssue,
    RecommendedAction,
    SlideEvaluationResult,
    SlideMeasurements,
    SlideStatus,
)


def extract_json_object(text: str) -> dict[str, Any]:
    """
    Parse a JSON object from model output.

    Tolerates leading/trailing whitespace and fenced markdown code blocks.
    """
    cleaned = text.strip()
    if not cleaned:
        raise MalformedVisionResponseError("Empty model response", raw_content=text)

    fence_match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError as inner_exc:
                raise MalformedVisionResponseError(
                    f"Invalid JSON in model response: {inner_exc}",
                    raw_content=text,
                ) from inner_exc
        else:
            raise MalformedVisionResponseError(
                f"Invalid JSON in model response: {exc}",
                raw_content=text,
            ) from exc

    if not isinstance(parsed, dict):
        raise MalformedVisionResponseError(
            "Model response JSON must be an object",
            raw_content=text,
        )
    return parsed


def _coerce_number(value: Any) -> int | float | None:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return None
    return None


def _parse_measurements(raw: Any) -> SlideMeasurements:
    if not isinstance(raw, dict):
        return SlideMeasurements()
    values: dict[str, int | float] = {}
    for key, value in raw.items():
        number = _coerce_number(value)
        if number is not None:
            values[str(key)] = number
    return SlideMeasurements(values=values)


def _parse_issue(raw: Any) -> LayoutIssue | None:
    if not isinstance(raw, dict):
        return None
    measurement_raw = raw.get("measurement") or {}
    measurement: dict[str, int | float] = {}
    if isinstance(measurement_raw, dict):
        for key, value in measurement_raw.items():
            number = _coerce_number(value)
            if number is not None:
                measurement[str(key)] = number

    confidence_raw = raw.get("confidence")
    confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else None

    return LayoutIssue(
        issue_id=str(raw.get("issue_id") or "UNKNOWN"),
        severity=str(raw.get("severity") or "minor"),
        confidence=confidence,
        affected_object=str(raw.get("affected_object") or ""),
        measurement=measurement,
        explanation=str(raw.get("explanation") or ""),
        recommended_action=RecommendedAction.from_raw(raw.get("recommended_action")),
    )


def _resolve_status(raw: dict[str, Any], issues: tuple[LayoutIssue, ...]) -> SlideStatus:
    status_raw = raw.get("status")
    if status_raw == SlideStatus.OK.value:
        return SlideStatus.OK if not issues else SlideStatus.NEEDS_ADJUSTMENT
    if status_raw == SlideStatus.NEEDS_ADJUSTMENT.value:
        return SlideStatus.NEEDS_ADJUSTMENT
    return SlideStatus.NEEDS_ADJUSTMENT if issues else SlideStatus.OK


def parse_slide_evaluation(raw: dict[str, Any]) -> SlideEvaluationResult:
    """Convert a parsed JSON object into a ``SlideEvaluationResult``."""
    issues_list = raw.get("issues") or []
    issues: list[LayoutIssue] = []
    if isinstance(issues_list, list):
        for entry in issues_list:
            issue = _parse_issue(entry)
            if issue is not None:
                issues.append(issue)

    slide_number_raw = raw.get("slide_number", raw.get("slide_index"))
    slide_number = int(slide_number_raw) if isinstance(slide_number_raw, (int, float)) else None

    issues_tuple = tuple(issues)
    status = _resolve_status(raw, issues_tuple)

    return SlideEvaluationResult(
        slide_number=slide_number,
        status=status,
        measurements=_parse_measurements(raw.get("measurements")),
        issues=issues_tuple,
        visual_notes=str(raw.get("visual_notes") or ""),
    )
