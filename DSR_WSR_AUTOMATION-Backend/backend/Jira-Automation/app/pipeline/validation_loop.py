"""Iterative render → vision evaluate → layout correct orchestration."""

from __future__ import annotations

from pathlib import Path

from app.pipeline.layout_corrector import VisionDrivenLayoutCorrector
from app.pipeline.protocols import (
    DeckGenerator,
    LayoutCorrector,
    PptRenderer,
    VisionClient,
)
from app.pipeline.types import (
    CorrectionResult,
    LoopIteration,
    PipelineConfig,
    ValidationLoopResult,
    VisionReport,
)


class IterativeValidationLoop:
    """
    Orchestrates the vision-based validation workflow.

    This class only coordinates injected collaborators — it does not perform
    layout modifications, rendering, or vision calls itself.

    Workflow (per iteration)
    ------------------------
    1. Render slides to PNG
    2. Vision evaluation
    3. Stop if no issues remain
    4. Otherwise delegate correction to ``LayoutCorrector`` and continue

    When ``content_json`` and ``output_ppt`` are supplied, the deck is generated
    once before the first iteration (existing layout engine, unchanged).
    """

    def __init__(
        self,
        renderer: PptRenderer,
        vision_client: VisionClient,
        corrector: LayoutCorrector,
        deck_generator: DeckGenerator | None = None,
    ) -> None:
        self._renderer = renderer
        self._vision_client = vision_client
        self._corrector = corrector
        self._deck_generator = deck_generator

    def run(
        self,
        ppt_path: Path | None = None,
        *,
        content_json: Path | None = None,
        output_ppt: Path | None = None,
        layout_hints: Path | None = None,
        config: PipelineConfig | None = None,
    ) -> ValidationLoopResult:
        """
        Run the iterative validation loop.

        Provide either ``ppt_path`` (existing deck) or both ``content_json`` and
        ``output_ppt`` (generate then validate).
        """
        cfg = config or PipelineConfig()
        ppt_path = self._resolve_ppt_path(
            ppt_path,
            content_json=content_json,
            output_ppt=output_ppt,
            layout_hints=layout_hints,
        )

        iterations: list[LoopIteration] = []
        final_report: VisionReport | None = None
        previous_correction: CorrectionResult | None = None

        for round_num in range(1, cfg.max_iterations + 1):
            render_batch = self._renderer.render_deck(
                ppt_path,
                output_dir=cfg.render_output_dir,
                keep_images=cfg.keep_render_images,
            )
            vision_report = self._vision_client.evaluate(render_batch)
            final_report = vision_report

            iteration = LoopIteration(
                iteration=round_num,
                render_batch=render_batch,
                vision_report=vision_report,
            )
            iterations.append(iteration)

            if self._vision_client.passes(vision_report):
                return ValidationLoopResult(
                    ppt_path=ppt_path,
                    passed=True,
                    iterations=iterations,
                    final_report=final_report,
                    stopped_reason="no_issues",
                )

            if round_num >= cfg.max_iterations:
                return ValidationLoopResult(
                    ppt_path=ppt_path,
                    passed=False,
                    iterations=iterations,
                    final_report=final_report,
                    stopped_reason="iteration_limit",
                )

            correction = self._corrector.correct(
                ppt_path,
                vision_report,
                content_json=content_json,
                **self._corrector_kwargs(render_batch),
            )
            iteration.correction = correction

            if not correction.modified:
                return ValidationLoopResult(
                    ppt_path=ppt_path,
                    passed=False,
                    iterations=iterations,
                    final_report=final_report,
                    stopped_reason="corrector_noop",
                )

            if self._is_negligible_change(correction, previous_correction, cfg):
                return ValidationLoopResult(
                    ppt_path=ppt_path,
                    passed=False,
                    iterations=iterations,
                    final_report=final_report,
                    stopped_reason="negligible_change",
                )

            previous_correction = correction
            ppt_path = correction.ppt_path.resolve()

        return ValidationLoopResult(
            ppt_path=ppt_path,
            passed=False,
            iterations=iterations,
            final_report=final_report,
            stopped_reason="iteration_limit",
        )

    def _resolve_ppt_path(
        self,
        ppt_path: Path | None,
        *,
        content_json: Path | None,
        output_ppt: Path | None,
        layout_hints: Path | None,
    ) -> Path:
        if content_json is not None and output_ppt is not None:
            if self._deck_generator is None:
                raise ValueError(
                    "Deck generation requested but no DeckGenerator was injected."
                )
            return self._deck_generator.generate(
                content_json,
                output_ppt,
                layout_hints=layout_hints,
            ).resolve()

        if ppt_path is None:
            raise ValueError(
                "Provide ppt_path or both content_json and output_ppt."
            )
        return ppt_path.resolve()

    def _corrector_kwargs(self, render_batch) -> dict:
        """Pass rendered image paths when the corrector supports them."""
        if not isinstance(self._corrector, VisionDrivenLayoutCorrector):
            return {}
        image_paths = {
            slide.slide_index: slide.image_path
            for slide in render_batch.slides
            if slide.image_path.is_file()
        }
        if not image_paths:
            return {}
        return {"image_paths": image_paths}

    @staticmethod
    def _is_negligible_change(
        correction: CorrectionResult,
        previous: CorrectionResult | None,
        config: PipelineConfig,
    ) -> bool:
        if not correction.actions_applied:
            return True
        if correction.change_magnitude_emu < config.negligible_change_emu:
            return True
        if (
            previous is not None
            and correction.actions_applied == previous.actions_applied
        ):
            return True
        return False
