"""Provider-agnostic chat LLM client (Gemini, Azure OpenAI, OpenAI, AWS Bedrock).

Set ``LLM_PROVIDER`` to ``auto`` (default), ``gemini``, ``azure``, ``openai``,
``bedrock``, or ``aws``. Credentials come from the matching env vars — switch
providers by editing ``.env`` only; call sites keep using ``create_llm_client()``
and ``client.chat.completions.create(...)``.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from openai import AzureOpenAI, OpenAI

from app.config import Settings, get_settings

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_PROVIDER_ALIASES = {
    "auto": "auto",
    "gemini": "gemini",
    "google": "gemini",
    "azure": "azure",
    "azure_openai": "azure",
    "openai": "openai",
    "bedrock": "bedrock",
    "aws": "bedrock",
    "aws_bedrock": "bedrock",
}


@dataclass(frozen=True)
class LLMClientInfo:
    """Resolved client plus the model/deployment id to pass to chat.completions."""

    client: Any
    model: str
    provider: str


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def normalize_provider(value: str | None) -> str:
    key = (value or "auto").strip().lower().replace("-", "_").replace(" ", "_")
    return _PROVIDER_ALIASES.get(key, key)


def provider_configured(provider: str, settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    provider = normalize_provider(provider)
    if provider == "gemini":
        return bool(s.gemini_api_key)
    if provider == "azure":
        return bool(s.azure_openai_endpoint and s.azure_openai_api_key)
    if provider == "openai":
        return bool(s.openai_api_key)
    if provider == "bedrock":
        return bool(s.aws_access_key_id and s.aws_secret_access_key and s.bedrock_model_id)
    return False


def detect_provider(settings: Settings | None = None) -> str | None:
    """Pick a provider from ``LLM_PROVIDER`` or the first configured credential set."""
    s = settings or get_settings()
    requested = normalize_provider(s.llm_provider)
    if requested != "auto":
        if requested not in {"gemini", "azure", "openai", "bedrock"}:
            raise ValueError(
                f"Unknown LLM_PROVIDER={s.llm_provider!r}. "
                "Use auto, gemini, azure, openai, or bedrock."
            )
        return requested if provider_configured(requested, s) else requested

    for candidate in ("gemini", "azure", "openai", "bedrock"):
        if provider_configured(candidate, s):
            return candidate
    return None


def resolve_model(provider: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    if s.llm_model:
        return s.llm_model
    if provider == "gemini":
        # Flash-Lite usually has more spare capacity than 3.8 Flash during demand spikes.
        return s.gemini_model or "gemini-3.5-flash-lite"
    if provider == "azure":
        return s.azure_openai_model or "gpt-4o-mini"
    if provider == "openai":
        return s.openai_model or "gpt-4o-mini"
    if provider == "bedrock":
        return s.bedrock_model_id or "amazon.nova-lite-v1:0"
    return "gpt-4o-mini"


def model_candidates(primary: str, settings: Settings | None = None) -> list[str]:
    """Primary model plus optional ``LLM_MODEL_FALLBACKS`` / ``GEMINI_MODEL_FALLBACKS``."""
    s = settings or get_settings()
    raw = _env("LLM_MODEL_FALLBACKS") or _env("GEMINI_MODEL_FALLBACKS")
    if not raw and normalize_provider(s.llm_provider) in {"auto", "gemini"}:
        # Sensible Gemini defaults when env does not list fallbacks.
        raw = "gemini-3.6-flash,gemini-3.8-flash,gemini-3.5-flash-lite"
    ordered: list[str] = []
    for name in [primary, *[part.strip() for part in raw.split(",") if part.strip()]]:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def is_transient_llm_error(exc: BaseException) -> bool:
    """True for overload / rate-limit style failures that may succeed on retry."""
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    if status in {408, 429, 500, 502, 503, 504}:
        return True
    text = str(exc).lower()
    markers = (
        "503",
        "429",
        "unavailable",
        "high demand",
        "overloaded",
        "resource_exhausted",
        "temporarily",
        "timeout",
        "timed out",
    )
    return any(marker in text for marker in markers)


def chat_completion_with_retries(
    client: Any,
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float = 0.3,
    response_format: dict[str, Any] | None = None,
    max_attempts: int | None = None,
    initial_delay_s: float | None = None,
) -> Any:
    """
    Call ``chat.completions.create`` with exponential backoff and model fallbacks.

    Retries help with Gemini/Azure ``503 high demand`` / ``429`` spikes.
    Raising the HTTP timeout alone does **not** fix capacity 503s; waiting/retrying
    and switching models does.
    """
    attempts = max_attempts
    if attempts is None:
        attempts = int(_env("LLM_RETRY_ATTEMPTS", "4") or "4")
    delay = initial_delay_s
    if delay is None:
        delay = float(_env("LLM_RETRY_INITIAL_DELAY_S", "1.5") or "1.5")

    candidates = model_candidates(model)
    last_error: BaseException | None = None

    for candidate in candidates:
        current_delay = delay
        for attempt in range(1, attempts + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": candidate,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if response_format is not None:
                    kwargs["response_format"] = response_format
                return client.chat.completions.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 — surface final error to caller
                last_error = exc
                if not is_transient_llm_error(exc) or attempt >= attempts:
                    break
                sleep_for = current_delay * (0.5 + random.random())
                time.sleep(sleep_for)
                current_delay = min(current_delay * 2, 30.0)

    if last_error is not None:
        raise last_error
    raise RuntimeError("LLM request failed with no exception detail")


def _build_gemini_client(settings: Settings) -> OpenAI:
    return OpenAI(
        api_key=settings.gemini_api_key,
        base_url=(settings.gemini_base_url or GEMINI_OPENAI_BASE_URL).rstrip("/") + "/",
    )


def _build_azure_client(settings: Settings) -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


def _build_openai_client(settings: Settings) -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _build_bedrock_client(settings: Settings) -> Any:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "AWS Bedrock requires boto3. Install with: pip install boto3"
        ) from exc

    session_kwargs: dict[str, str] = {
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
        "region_name": settings.aws_region or "us-east-1",
    }
    if settings.aws_session_token:
        session_kwargs["aws_session_token"] = settings.aws_session_token
    runtime = boto3.client("bedrock-runtime", **session_kwargs)
    return _BedrockOpenAICompatClient(runtime)


class _BedrockOpenAICompatClient:
    """Minimal OpenAI-shaped wrapper around Bedrock Converse."""

    def __init__(self, runtime: Any) -> None:
        self.chat = SimpleNamespace(completions=self)
        self._runtime = runtime

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int = 256,
        temperature: float = 0.3,
        response_format: dict[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        system_parts: list[str] = []
        converse_messages: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role") or "user"
            content = message.get("content") or ""
            if isinstance(content, list):
                # Vision-style parts are not mapped here; flatten text only.
                content = " ".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            if role == "system":
                system_parts.append(str(content))
                continue
            mapped_role = "assistant" if role == "assistant" else "user"
            converse_messages.append(
                {"role": mapped_role, "content": [{"text": str(content)}]}
            )

        if response_format and response_format.get("type") == "json_object":
            system_parts.append("Respond with valid JSON only. No markdown fences.")

        kwargs: dict[str, Any] = {
            "modelId": model,
            "messages": converse_messages
            or [{"role": "user", "content": [{"text": ""}]}],
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_parts:
            kwargs["system"] = [{"text": "\n\n".join(system_parts)}]

        raw = self._runtime.converse(**kwargs)
        text_chunks: list[str] = []
        for block in raw.get("output", {}).get("message", {}).get("content", []):
            if isinstance(block, dict) and "text" in block:
                text_chunks.append(block["text"])
        content = "".join(text_chunks)
        # Keep a tiny OpenAI-like shape for existing call sites.
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            raw=raw,
        )


def create_llm_client(
    settings: Settings | None = None,
) -> tuple[Any, str] | tuple[None, None]:
    """
    Return ``(client, model_or_deployment)`` for chat completions.

    ``client`` always supports ``client.chat.completions.create(...)``.
    """
    s = settings or get_settings()
    provider = detect_provider(s)
    if provider is None:
        return None, None

    if not provider_configured(provider, s):
        return None, None

    model = resolve_model(provider, s)
    if provider == "gemini":
        return _build_gemini_client(s), model
    if provider == "azure":
        return _build_azure_client(s), model
    if provider == "openai":
        return _build_openai_client(s), model
    if provider == "bedrock":
        return _build_bedrock_client(s), model
    return None, None


def llm_credentials_help() -> str:
    return (
        "Set LLM_PROVIDER=auto|gemini|azure|openai|bedrock and the matching key(s): "
        "GEMINI_API_KEY; or AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY; "
        "or OPENAI_API_KEY; or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + BEDROCK_MODEL_ID. "
        "Optional: LLM_MODEL to override the model/deployment name."
    )


def dump_llm_config(settings: Settings | None = None) -> dict[str, Any]:
    """Non-secret diagnostics for probe scripts / logging."""
    s = settings or get_settings()
    provider = detect_provider(s)
    return {
        "llm_provider_setting": s.llm_provider or "auto",
        "resolved_provider": provider,
        "resolved_model": resolve_model(provider, s) if provider else None,
        "gemini_key_set": bool(s.gemini_api_key),
        "azure_configured": provider_configured("azure", s),
        "openai_key_set": bool(s.openai_api_key),
        "bedrock_configured": provider_configured("bedrock", s),
    }
