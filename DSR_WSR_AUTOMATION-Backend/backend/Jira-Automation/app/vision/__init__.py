"""Vision-based slide image evaluation."""

from app.vision.client import VisionClient, VisionClientConfig
from app.vision.exceptions import (
    MalformedVisionResponseError,
    VisionClientError,
    VisionConfigurationError,
    VisionModelError,
    VisionTimeoutError,
)
from app.vision.parser import extract_json_object, parse_slide_evaluation
from app.vision.transport import GeminiVisionTransport, OpenAIVisionTransport, VisionModelTransport
from app.vision.types import (
    LayoutIssue,
    RecommendedAction,
    SlideEvaluationResult,
    SlideMeasurements,
    SlideStatus,
)

__all__ = [
    "LayoutIssue",
    "MalformedVisionResponseError",
    "GeminiVisionTransport",
    "OpenAIVisionTransport",
    "RecommendedAction",
    "SlideEvaluationResult",
    "SlideMeasurements",
    "SlideStatus",
    "VisionClient",
    "VisionClientConfig",
    "VisionClientError",
    "VisionConfigurationError",
    "VisionModelError",
    "VisionModelTransport",
    "VisionTimeoutError",
    "extract_json_object",
    "parse_slide_evaluation",
]
