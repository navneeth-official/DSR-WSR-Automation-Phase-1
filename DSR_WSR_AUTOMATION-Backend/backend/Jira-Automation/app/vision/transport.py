"""LLM transport layer for vision evaluation (injectable)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.constants.vision_layout_inspector_prompt import VISION_LAYOUT_INSPECTOR_SYSTEM_PROMPT


@runtime_checkable
class VisionModelTransport(Protocol):
    """Low-level interface for sending images to a vision-capable chat model."""

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_content: list[dict[str, Any]],
        temperature: float,
        timeout_s: float,
    ) -> str:
        """Return the model's message content as a string."""
        ...


@dataclass(frozen=True)
class GeminiVisionTransport:
    """Google Gemini vision transport via unified llm_client."""

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_content: list[dict[str, Any]],
        temperature: float,
        timeout_s: float,
    ) -> str:
        from app.services.llm_client import complete_vision_json

        return complete_vision_json(
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=temperature,
            timeout_s=timeout_s,
        )


@dataclass(frozen=True)
class OpenAIVisionTransport:
    """OpenAI / Azure OpenAI chat completions transport."""

    client: Any
    model: str

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_content: list[dict[str, Any]],
        temperature: float,
        timeout_s: float,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
            timeout=timeout_s,
        )
        return response.choices[0].message.content or ""


def encode_image_base64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def build_user_content(
    *,
    image_path: Path,
    template_image_path: Path | None,
    slide_number: int | None,
    context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Build multimodal user message content for one slide evaluation."""
    payload: dict[str, Any] = {
        "instruction": (
            "Inspect the rendered slide image and return JSON for this slide only."
        ),
        "image_path": str(image_path),
    }
    if slide_number is not None:
        payload["slide_number"] = slide_number
    if context:
        payload.update(context)

    if template_image_path is not None:
        payload["template_reference"] = (
            "A reference template image is provided for visual comparison. "
            "Measure the rendered slide against expected placeholder positions."
        )

    content: list[dict[str, Any]] = [
        {"type": "text", "text": json.dumps(payload, ensure_ascii=False)},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{encode_image_base64(image_path)}",
                "detail": "high",
            },
        },
    ]

    if template_image_path is not None:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:image/png;base64,"
                        f"{encode_image_base64(template_image_path)}"
                    ),
                    "detail": "high",
                },
            }
        )

    return content


def default_system_prompt() -> str:
    return VISION_LAYOUT_INSPECTOR_SYSTEM_PROMPT
