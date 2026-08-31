"""Unified LLM client for Gemini and Azure/OpenAI (text + vision)."""

from __future__ import annotations

import base64
import re
from typing import Any

from openai import AzureOpenAI, OpenAI

from app.config import get_settings, llm_configured, resolve_llm_provider
from app.services.llm_rate_limiter import maybe_acquire_wsr_rate_limit

_LLM_NOT_CONFIGURED = (
    "LLM not configured. Set GEMINI_API_KEY, or AZURE_OPENAI_ENDPOINT + "
    "AZURE_OPENAI_API_KEY, or OPENAI_API_KEY in .env"
)


def create_openai_client() -> tuple[OpenAI | AzureOpenAI, str] | tuple[None, None]:
    """Return (client, model_or_deployment_name) for Azure/OpenAI chat APIs."""
    settings = get_settings()

    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        deployment = settings.azure_openai_model or "gpt-4o-mini"
        return client, deployment

    if settings.openai_api_key:
        return OpenAI(api_key=settings.openai_api_key), "gpt-4o-mini"

    return None, None


def create_gemini_client() -> Any | None:
    """Return a Google GenAI client when GEMINI_API_KEY is set."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return None

    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def resolve_text_model() -> str:
    """Return the model/deployment name for the active text provider."""
    settings = get_settings()
    provider = resolve_llm_provider()
    if provider == "gemini":
        return settings.gemini_model
    _, model = create_openai_client()
    return model or settings.azure_openai_model or "gpt-4o-mini"


def resolve_vision_model() -> str:
    """Return the model name for vision/multimodal calls."""
    settings = get_settings()
    provider = resolve_llm_provider()
    if provider == "gemini":
        return settings.gemini_vision_model or settings.gemini_model
    # Legacy OpenAI/Azure vision env vars when not on Gemini.
    return (
        settings.azure_openai_vision_model
        or settings.openai_vision_model
        or settings.azure_openai_model
        or "gpt-4o"
    )


def complete_text(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_output_tokens: int | None = None,
    json_mode: bool = False,
) -> str:
    """Run a text completion and return the model response string."""
    maybe_acquire_wsr_rate_limit()
    provider = resolve_llm_provider()
    if provider == "gemini":
        return _gemini_complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            json_mode=json_mode,
        )
    if provider in {"azure", "openai"}:
        return _openai_complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            json_mode=json_mode,
        )
    raise RuntimeError(_LLM_NOT_CONFIGURED)


def complete_vision_json(
    *,
    system_prompt: str,
    user_content: list[dict[str, Any]],
    temperature: float = 0.1,
    timeout_s: float = 120.0,
) -> str:
    """Run a multimodal completion and return JSON text."""
    maybe_acquire_wsr_rate_limit()
    provider = resolve_llm_provider()
    if provider == "gemini":
        return _gemini_complete_vision_json(
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=temperature,
            timeout_s=timeout_s,
        )
    if provider in {"azure", "openai"}:
        return _openai_complete_vision_json(
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=temperature,
            timeout_s=timeout_s,
        )
    raise RuntimeError(_LLM_NOT_CONFIGURED)


def _gemini_complete_text(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_output_tokens: int | None,
    json_mode: bool,
) -> str:
    from google.genai import types

    client = create_gemini_client()
    if client is None:
        raise RuntimeError(_LLM_NOT_CONFIGURED)

    settings = get_settings()
    config_kwargs: dict[str, Any] = {
        "system_instruction": system_prompt,
        "temperature": temperature,
    }
    if max_output_tokens is not None:
        config_kwargs["max_output_tokens"] = max_output_tokens
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text or ""


def _openai_complete_text(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_output_tokens: int | None,
    json_mode: bool,
) -> str:
    client, model = create_openai_client()
    if client is None or not model:
        raise RuntimeError(_LLM_NOT_CONFIGURED)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    if max_output_tokens is not None:
        kwargs["max_tokens"] = max_output_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _gemini_complete_vision_json(
    *,
    system_prompt: str,
    user_content: list[dict[str, Any]],
    temperature: float,
    timeout_s: float,
) -> str:
    from google.genai import types

    client = create_gemini_client()
    if client is None:
        raise RuntimeError(_LLM_NOT_CONFIGURED)

    settings = get_settings()
    parts = _openai_user_content_to_gemini_parts(user_content)
    config_kwargs: dict[str, Any] = {
        "system_instruction": system_prompt,
        "temperature": temperature,
        "response_mime_type": "application/json",
    }
    try:
        config_kwargs["http_options"] = types.HttpOptions(timeout=int(timeout_s * 1000))
    except (AttributeError, TypeError, ValueError):
        pass

    response = client.models.generate_content(
        model=settings.gemini_vision_model or settings.gemini_model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text or ""


def _openai_complete_vision_json(
    *,
    system_prompt: str,
    user_content: list[dict[str, Any]],
    temperature: float,
    timeout_s: float,
) -> str:
    client, model = create_openai_client()
    if client is None or not model:
        raise RuntimeError(_LLM_NOT_CONFIGURED)

    vision_model = resolve_vision_model()
    response = client.chat.completions.create(
        model=vision_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
        timeout=timeout_s,
    )
    return response.choices[0].message.content or ""


def _openai_user_content_to_gemini_parts(
    user_content: list[dict[str, Any]],
) -> list[Any]:
    from google.genai import types

    parts: list[Any] = []
    for item in user_content:
        item_type = item.get("type")
        if item_type == "text":
            parts.append(types.Part.from_text(text=item.get("text", "")))
            continue
        if item_type == "image_url":
            url = (item.get("image_url") or {}).get("url", "")
            match = re.match(r"^data:(image/[^;]+);base64,(.+)$", url, re.DOTALL)
            if not match:
                raise ValueError(f"Unsupported image URL format for Gemini: {url[:80]}")
            mime_type, encoded = match.group(1), match.group(2)
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(encoded),
                    mime_type=mime_type,
                )
            )
            continue
        raise ValueError(f"Unsupported user content part type for Gemini: {item_type}")
    return parts


# Backward-compatible aliases used by older imports.
def create_llm_client() -> tuple[OpenAI | AzureOpenAI, str] | tuple[None, None]:
    return create_openai_client()


__all__ = [
    "complete_text",
    "complete_vision_json",
    "create_gemini_client",
    "create_llm_client",
    "create_openai_client",
    "llm_configured",
    "resolve_llm_provider",
    "resolve_text_model",
    "resolve_vision_model",
]
