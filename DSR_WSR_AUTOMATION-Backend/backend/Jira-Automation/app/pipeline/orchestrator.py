"""High-level pipeline: generate deck then optionally run validation loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from app.pipeline.dependencies import PipelineDependencies
from app.pipeline.types import (
    HybridValidationResult,
    PipelineConfig,
    PipelineMode,
    ValidationLoopResult,
)

ValidationResult = Union[ValidationLoopResult, HybridValidationResult]


class VisionLayoutPipeline:
    """
    End-to-end entry point that composes existing and new stages.

    Stage 1 — Generate PPT (existing layout engine, unchanged)
    Stage 2 — Validation loop (hybrid or legacy), optional
    """

    def __init__(self, dependencies: PipelineDependencies | None = None) -> None:
        self._deps = dependencies or PipelineDependencies.create_default()

    @property
    def pipeline_mode(self) -> PipelineMode:
        return self._deps.pipeline_mode

    def generate_deck(
        self,
        content_json: Path,
        output_ppt: Path,
        *,
        layout_hints: Path | None = None,
    ) -> Path:
        """Run the estimate-based layout engine (``update_delivery_status.py``)."""
        return self._deps.deck_generator.generate(
            content_json,
            output_ppt,
            layout_hints=layout_hints,
        )

    def validate_and_correct(
        self,
        ppt_path: Path | None = None,
        *,
        content_json: Path | None = None,
        output_ppt: Path | None = None,
        layout_hints: Path | None = None,
        config: PipelineConfig | None = None,
    ) -> ValidationResult:
        """Run the configured validation loop (hybrid by default)."""
        if self._deps.pipeline_mode == PipelineMode.HYBRID:
            return self._deps.hybrid_validation_loop.run(
                ppt_path,
                content_json=content_json,
                output_ppt=output_ppt,
                layout_hints=layout_hints,
                config=config,
            )
        return self._deps.validation_loop.run(
            ppt_path,
            content_json=content_json,
            output_ppt=output_ppt,
            layout_hints=layout_hints,
            config=config,
        )

    def generate_validate(
        self,
        content_json: Path,
        output_ppt: Path,
        *,
        layout_hints: Path | None = None,
        run_validation: bool = True,
        config: PipelineConfig | None = None,
        validation_log: Path | None = None,
    ) -> tuple[Path, ValidationResult | None]:
        """
        Generate then run the validation loop.

        Returns ``(final_presentation, validation_result)``.
        """
        cfg = config or PipelineConfig()

        if not run_validation:
            ppt_path = self.generate_deck(
                content_json,
                output_ppt,
                layout_hints=layout_hints,
            )
            return ppt_path, None

        loop_result = self.validate_and_correct(
            content_json=content_json,
            output_ppt=output_ppt,
            layout_hints=layout_hints,
            config=cfg,
        )

        if validation_log:
            validation_log.parent.mkdir(parents=True, exist_ok=True)
            validation_log.write_text(
                json.dumps(loop_result.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return loop_result.final_presentation, loop_result
