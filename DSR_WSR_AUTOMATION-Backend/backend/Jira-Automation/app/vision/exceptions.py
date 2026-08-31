"""Exceptions raised by the vision evaluation client."""

from __future__ import annotations


class VisionClientError(Exception):
    """Base error for vision evaluation failures."""


class VisionConfigurationError(VisionClientError):
    """Raised when LLM credentials or model configuration is missing."""


class MalformedVisionResponseError(VisionClientError):
    """Raised when the model returns content that cannot be parsed as JSON."""

    def __init__(self, message: str, *, raw_content: str = "") -> None:
        super().__init__(message)
        self.raw_content = raw_content


class VisionModelError(VisionClientError):
    """Raised when the vision model API call fails after retries."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class VisionTimeoutError(VisionModelError):
    """Raised when a vision model request exceeds the configured timeout."""
