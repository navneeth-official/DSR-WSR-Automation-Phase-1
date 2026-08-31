"""Qualitative vision client — visual review only, no measurements."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.constants.vision_qualitative_reviewer_prompt import (
    QUALITATIVE_VISION_REVIEWER_PROMPT,
)
from app.vision.client import VisionClient, VisionClientConfig, _is_retryable
from app.vision.exceptions import MalformedVisionResponseError, VisionModelError
from app.vision.logging import log_vision_error, log_vision_request, log_vision_response
from app.vision.parser import extract_json_object
from app.vision.qualitative_parser import parse_qualitative_review
from app.vision.qualitative_types import QualitativeSlideReview
from app.vision.transport import build_user_content


class QualitativeVisionClient:
    """
    GPT-4o visual quality reviewer.

    Returns qualitative findings only — never pixel coordinates or movement deltas.
    """

    def __init__(
        self,
        *,
        vision_client: VisionClient | None = None,
        model: str = "gpt-4o",
    ) -> None:
        self._client = vision_client or VisionClient(
            config=VisionClientConfig(model=model),
            system_prompt=QUALITATIVE_VISION_REVIEWER_PROMPT,
        )

    @property
    def model_name(self) -> str:
        return self._client.model_name

    def review_slide(
        self,
        image_path: Path | str,
        *,
        slide_number: int | None = None,
        title: str = "",
        layout_context: dict | None = None,
    ) -> QualitativeSlideReview:
        image = Path(image_path).resolve()
        if not image.is_file():
            raise FileNotFoundError(f"Slide image not found: {image}")

        context: dict = {"title": title, "review_mode": "qualitative"}
        if layout_context:
            context["layout_hints"] = layout_context

        user_content = build_user_content(
            image_path=image,
            template_image_path=None,
            slide_number=slide_number,
            context=context,
        )
        raw = self._call_with_retries(
            user_content,
            slide_number=slide_number,
            image_path=image,
        )
        review = parse_qualitative_review(raw)
        if review.slide_number is None and slide_number is not None:
            return QualitativeSlideReview(
                slide_number=slide_number,
                status=review.status,
                overall_quality=review.overall_quality,
                issues=review.issues,
            )
        return review

    def _call_with_retries(
        self,
        user_content: list[dict[str, Any]],
        *,
        slide_number: int | None,
        image_path: Path,
    ) -> dict[str, Any]:
        cfg = self._client.config
        transport = self._client._transport  # noqa: SLF001
        delay = cfg.retry_delay_s
        last_parse: MalformedVisionResponseError | None = None

        for attempt in range(1, cfg.json_max_attempts + 1):
            try:
                log_vision_request(
                    model=self.model_name,
                    slide_number=slide_number,
                    image_path=image_path,
                    user_payload={"mode": "qualitative"},
                )
                content = transport.complete_json(
                    system_prompt=QUALITATIVE_VISION_REVIEWER_PROMPT,
                    user_content=user_content,
                    temperature=cfg.temperature,
                    timeout_s=cfg.timeout_s,
                )
                log_vision_response(
                    model=self.model_name,
                    slide_number=slide_number,
                    content=content,
                    attempt=attempt,
                )
                return extract_json_object(content)
            except MalformedVisionResponseError as exc:
                last_parse = exc
                log_vision_error(
                    model=self.model_name,
                    slide_number=slide_number,
                    attempt=attempt,
                    error=str(exc),
                )
            except Exception as exc:
                log_vision_error(
                    model=self.model_name,
                    slide_number=slide_number,
                    attempt=attempt,
                    error=str(exc),
                )
                if _is_retryable(exc) and attempt < cfg.api_max_retries:
                    time.sleep(delay)
                    delay *= cfg.retry_backoff
                    continue
                raise VisionModelError(f"Qualitative vision failed: {exc}", cause=exc) from exc
            time.sleep(delay)
            delay *= cfg.retry_backoff

        if last_parse is not None:
            raise last_parse
        raise VisionModelError("Qualitative vision request failed")
