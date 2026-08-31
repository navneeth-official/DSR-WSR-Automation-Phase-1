"""Unit tests for vision measurement → EMU mapping."""

from __future__ import annotations

import json
from pathlib import Path

from app.layout.config import LayoutCorrectorConfig
from app.layout.measurement_mapper import VisionMeasurementMapper
from app.layout.shape_ops import PixelScale
from app.vision.parser import parse_slide_evaluation

# Standard 16:9 slide (10 x 7.5 in) at 1920x1080 export scale.
SLIDE_HEIGHT_EMU = 6_858_000
SLIDE_WIDTH_EMU = 9_144_000


def _mapper() -> VisionMeasurementMapper:
    scale = PixelScale(
        slide_width_emu=SLIDE_WIDTH_EMU,
        slide_height_emu=SLIDE_HEIGHT_EMU,
        image_width_px=1920,
        image_height_px=1080,
    )
    return VisionMeasurementMapper(scale, LayoutCorrectorConfig())


def test_gap_excess_uses_gap_pixels_not_fixed_fallback():
    mapper = _mapper()
    slide = {
        "gap_between_sections": 40,
        "last_highlight_text_bottom": 500,
        "keyactivities_title_top": 540,
    }
    issue = {"gap_pixels": 40}
    excess = mapper.gap_excess_emu(slide, issue)
    assert excess is not None and excess > 0
    # Must not equal the old fixed 0.15 in fallback (137160 EMU).
    assert excess != mapper.min_gap_emu


def test_move_section_up_delta_is_measurement_based():
    mapper = _mapper()
    slide_data = {
        "slide_number": 3,
        "status": "needs_adjustment",
        "measurements": {
            "gap_between_sections": 40,
            "unused_space_inside_highlight": 20,
            "last_highlight_text_bottom": 500,
            "keyactivities_title_top": 540,
        },
        "issues": [
            {
                "issue_id": "KA001",
                "severity": "low",
                "affected_object": "Key Activities",
                "measurement": {"gap_pixels": 40},
                "explanation": "excessive gap",
                "recommended_action": "move_section_up",
            }
        ],
    }
    evaluation = parse_slide_evaluation(slide_data)
    excess = mapper.gap_excess_emu(evaluation.measurements, evaluation.issues[0].measurement)
    assert excess == mapper.px_to_emu_y(40) - mapper.min_gap_emu


def test_unused_space_pixels_used_for_shrink():
    mapper = _mapper()
    issue = {"unused_space_pixels": 20}
    slide = {"unused_space_inside_highlight": 20}
    shrink = mapper.hl_shrink_to_remove_emu(slide, issue)
    assert shrink == mapper.px_to_emu_y(20)


def test_overlap_computed_from_measurements_when_issue_missing_overlap():
    mapper = _mapper()
    # KA starts 10px before required clearance after text bottom.
    slide = {
        "last_highlight_text_bottom": 500,
        "keyactivities_title_top": 500 + mapper.min_gap_px - 10,
    }
    overlap = mapper.overlap_emu(slide, {})
    assert overlap is not None
    assert overlap == mapper.px_to_emu_y(10)


def test_vision_loop_json_slide3_mappings():
    loop_path = Path(__file__).resolve().parents[2] / "HEB_Delivery_Status.vision_loop.json"
    if not loop_path.is_file():
        return
    payload = json.loads(loop_path.read_text(encoding="utf-8"))
    slide_data = payload["final_validation_report"]["slides"][0]
    evaluation = parse_slide_evaluation(slide_data)
    mapper = _mapper()

    shrink = mapper.hl_shrink_to_remove_emu(
        evaluation.measurements,
        evaluation.issues[0].measurement,
    )
    assert shrink == mapper.px_to_emu_y(20)

    excess = mapper.gap_excess_emu(
        evaluation.measurements,
        evaluation.issues[1].measurement,
    )
    assert excess is not None and excess > 0
