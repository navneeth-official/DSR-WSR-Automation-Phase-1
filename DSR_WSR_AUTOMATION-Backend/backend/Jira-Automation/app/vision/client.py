"""Vision model client for single-slide image evaluation."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import llm_configured, resolve_llm_provider
from app.services.llm_client import create_openai_client, resolve_vision_model
from app.vision.exceptions import (
    MalformedVisionResponseError,
    VisionConfigurationError,
    VisionModelError,
    VisionTimeoutError,
)
from app.vision.logging import (
    configure_vision_logging,
    default_log_path,
    log_vision_error,
    log_vision_request,
    log_vision_response,
)
from app.vision.parser import extract_json_object, parse_slide_evaluation
from app.vision.transport import (
    GeminiVisionTransport,
    OpenAIVisionTransport,
    VisionModelTransport,
    build_user_content,
    default_system_prompt,
)
from app.vision.types import SlideEvaluationResult

DEFAULT_VISION_MODEL = "gpt-4o"


def _resolve_vision_model(configured: str | None) -> str:
    if configured and configured != DEFAULT_VISION_MODEL:
        return configured
    return resolve_vision_model()


def _is_retryable(exc: Exception) -> bool:
    name = type(exc).__name__
    if name in {"APITimeoutError", "APIConnectionError", "RateLimitError", "TimeoutError"}:
        return True
    status_code = getattr(exc, "status_code", None)
    return status_code in {429, 500, 502, 503, 504}


@dataclass
class VisionClientConfig:
    model: str = DEFAULT_VISION_MODEL
    json_max_attempts: int = 2  # initial call + one retry on invalid JSON
    api_max_retries: int = 3
    retry_delay_s: float = 1.0
    retry_backoff: float = 2.0
    timeout_s: float = 120.0
    temperature: float = 0.1
    log_path: Path | None = None


class VisionClient:
    """
    Evaluate rendered slide images with a vision-capable language model.

    This client has no knowledge of PowerPoint files or layout correction.
    It accepts image paths, calls the configured model, and returns typed results.
    """

    def __init__(
        self,
        *,
        transport: VisionModelTransport | None = None,
        config: VisionClientConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self._config = config or VisionClientConfig()
        self._system_prompt = system_prompt or default_system_prompt()
        self._model_name = _resolve_vision_model(self._config.model)
        configure_vision_logging(
            log_path=self._config.log_path or default_log_path(),
        )
        self._transport = transport or self._build_default_transport()

    @property
    def config(self) -> VisionClientConfig:
        return self._config

    @property
    def model_name(self) -> str:
        return self._model_name

    def evaluate(
        self,
        image: Path | str,
        *,
        template_image: Path | str | None = None,
        slide_number: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> SlideEvaluationResult:
        """
        Inspect one rendered slide image and return a typed evaluation result.

        Args:
            image: Path to the rendered slide PNG.
            template_image: Optional reference template image for comparison.
            slide_number: Optional slide index included in the user prompt.
            context: Optional extra JSON-serializable context for the model.
        """
        image_path = Path(image).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Slide image not found: {image_path}")

        template_path: Path | None = None
        if template_image is not None:
            template_path = Path(template_image).resolve()
            if not template_path.is_file():
                raise FileNotFoundError(
                    f"Template image not found: {template_path}"
                )

        user_content = build_user_content(
            image_path=image_path,
            template_image_path=template_path,
            slide_number=slide_number,
            context=context,
        )

        raw_json = self._call_with_retries(
            user_content,
            slide_number=slide_number,
            image_path=image_path,
        )
        return parse_slide_evaluation(raw_json)

    def _build_default_transport(self) -> VisionModelTransport:
        if not llm_configured():
            raise VisionConfigurationError(
                "LLM not configured. Set GEMINI_API_KEY, or AZURE_OPENAI_ENDPOINT + "
                "AZURE_OPENAI_API_KEY, or OPENAI_API_KEY in .env"
            )

        provider = resolve_llm_provider()
        self._model_name = resolve_vision_model()

        if provider == "gemini":
            return GeminiVisionTransport()

        client, deployment = create_openai_client()
        if client is None:
            raise VisionConfigurationError(
                "LLM not configured. Set GEMINI_API_KEY, or AZURE_OPENAI_ENDPOINT + "
                "AZURE_OPENAI_API_KEY, or OPENAI_API_KEY in .env"
            )

        model = self._model_name
        if (
            os.getenv("AZURE_OPENAI_ENDPOINT")
            and not os.getenv("AZURE_OPENAI_VISION_MODEL")
            and deployment
            and model == DEFAULT_VISION_MODEL
        ):
            model = deployment
        self._model_name = model
        return OpenAIVisionTransport(client=client, model=model)

    def _call_with_retries(
        self,
        user_content: list[dict[str, Any]],
        *,
        slide_number: int | None,
        image_path: Path,
    ) -> dict[str, Any]:
        user_payload = _payload_from_user_content(user_content)
        delay = self._config.retry_delay_s
        last_model_error: Exception | None = None
        last_parse_error: MalformedVisionResponseError | None = None

        for attempt in range(1, self._config.json_max_attempts + 1):
            try:
                log_vision_request(
                    model=self._model_name,
                    slide_number=slide_number,
                    image_path=image_path,
                    user_payload=user_payload,
                )
                content = self._transport.complete_json(
                    system_prompt=self._system_prompt,
                    user_content=user_content,
                    temperature=self._config.temperature,
                    timeout_s=self._config.timeout_s,
                )
                log_vision_response(
                    model=self._model_name,
                    slide_number=slide_number,
                    content=content,
                    attempt=attempt,
                )
                return extract_json_object(content)
            except MalformedVisionResponseError as exc:
                last_parse_error = exc
                log_vision_error(
                    model=self._model_name,
                    slide_number=slide_number,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt >= self._config.json_max_attempts:
                    break
            except Exception as exc:
                log_vision_error(
                    model=self._model_name,
                    slide_number=slide_number,
                    attempt=attempt,
                    error=str(exc),
                )
                if self._retry_api_error(exc, attempt):
                    last_model_error = exc
                    if attempt >= self._config.api_max_retries:
                        break
                    time.sleep(delay)
                    delay *= self._config.retry_backoff
                    continue
                if type(exc).__name__ == "APITimeoutError":
                    raise VisionTimeoutError(
                        f"Vision model request timed out after "
                        f"{self._config.timeout_s}s",
                        cause=exc,
                    ) from exc
                raise VisionModelError(
                    f"Vision model request failed: {exc}",
                    cause=exc,
                ) from exc

            time.sleep(delay)
            delay *= self._config.retry_backoff

        if last_parse_error is not None:
            raise last_parse_error
        if last_model_error is not None:
            raise VisionModelError(
                f"Vision model request failed after {self._config.api_max_retries} "
                f"attempt(s): {last_model_error}",
                cause=last_model_error,
            ) from last_model_error

        raise VisionModelError("Vision model request failed for an unknown reason")

    def _retry_api_error(self, exc: Exception, attempt: int) -> bool:
        if attempt >= self._config.api_max_retries:
            return False
        return _is_retryable(exc)


def _payload_from_user_content(user_content: list[dict[str, Any]]) -> dict[str, Any]:
    import json

    for part in user_content:
        if part.get("type") == "text":
            try:
                return json.loads(part.get("text") or "{}")
            except json.JSONDecodeError:
                return {"raw": part.get("text", "")}
    return {}
