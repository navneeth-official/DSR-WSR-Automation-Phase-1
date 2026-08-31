"""Pipeline adapters and bridges for layout correction."""

from __future__ import annotations

from pathlib import Path

from app.layout import LayoutCorrector, SlideCorrectionInput
from app.pipeline.types import CorrectionResult, VisionReport
from app.vision.parser import parse_slide_evaluation


def vision_report_to_inputs(
    report: VisionReport,
    *,
    image_paths: dict[int, Path] | None = None,
) -> list[SlideCorrectionInput]:
    """Build slide correction inputs from a pipeline vision report."""
    image_paths = image_paths or {}
    inputs: list[SlideCorrectionInput] = []
    for slide_data in report.slides:
        evaluation = parse_slide_evaluation(slide_data)
        slide_index = int(
            slide_data.get("slide_index")
            or evaluation.slide_number
            or 0
        )
        inputs.append(
            SlideCorrectionInput(
                evaluation=evaluation,
                image_path=image_paths.get(slide_index) if slide_index else None,
            )
        )
    return inputs


class NullLayoutCorrector:
    """
    Placeholder corrector for architecture wiring.

    Does not modify the deck.
    """

    def correct(
        self,
        ppt_path: Path,
        report: VisionReport,
        *,
        content_json: Path | None = None,
    ) -> CorrectionResult:
        del content_json
        issue_count = sum(len(s.get("issues") or []) for s in report.slides)
        return CorrectionResult(
            modified=False,
            ppt_path=ppt_path,
            actions_applied=[],
            message=(
                "No layout corrector configured; vision report recorded only "
                f"({issue_count} issue(s) across {len(report.slides)} slide(s))."
            ),
            details={"issue_count": issue_count},
        )


class VisionDrivenLayoutCorrector:
    """Pipeline adapter wrapping ``app.layout.LayoutCorrector``."""

    def __init__(
        self,
        *,
        corrector: LayoutCorrector | None = None,
        image_paths: dict[int, Path] | None = None,
    ) -> None:
        self._corrector = corrector or LayoutCorrector()
        self._image_paths = image_paths or {}

    def correct(
        self,
        ppt_path: Path,
        report: VisionReport,
        *,
        content_json: Path | None = None,
        image_paths: dict[int, Path] | None = None,
    ) -> CorrectionResult:
        del content_json
        paths = image_paths or self._image_paths
        inputs = vision_report_to_inputs(report, image_paths=paths)
        if not inputs:
            return CorrectionResult(
                modified=False,
                ppt_path=ppt_path,
                message="No slides in vision report to correct.",
            )

        result = self._corrector.correct(ppt_path, inputs, save=True)
        pipeline_result = result.to_correction_result()
        if result.failures:
            pipeline_result.message += f" ({len(result.failures)} failure(s))"
        return pipeline_result


class LegacyRepairLayoutCorrector:
    """
    Optional bridge to the existing rulebook repair loop.

    Keeps current spacing/positioning logic in ``ppt_format_repair*`` modules.
    """

    def __init__(self, *, max_rounds: int = 1, pass_threshold: float = 80) -> None:
        self._max_rounds = max_rounds
        self._pass_threshold = pass_threshold

    def correct(
        self,
        ppt_path: Path,
        report: VisionReport,
        *,
        content_json: Path | None = None,
    ) -> CorrectionResult:
        del report
        if content_json is None or not content_json.is_file():
            return CorrectionResult(
                modified=False,
                ppt_path=ppt_path,
                message="Legacy repair requires content_json path.",
            )

        from app.services.ppt_format_repair_loop import repair_deck_until_pass

        repair_result = repair_deck_until_pass(
            ppt_path,
            content_json,
            max_rounds=self._max_rounds,
            pass_threshold=self._pass_threshold,
        )
        return CorrectionResult(
            modified=bool(repair_result.rounds),
            ppt_path=Path(repair_result.ppt_path),
            actions_applied=[
                action
                for rnd in repair_result.rounds
                for action in (rnd.get("actions") or [])
            ],
            message="Applied legacy rulebook repair pass.",
            details=repair_result.to_dict(),
        )
