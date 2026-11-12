from app.config import Settings
from app.services.llm_client import (
    detect_provider,
    is_transient_llm_error,
    model_candidates,
    normalize_provider,
    resolve_model,
)


def _settings(**kwargs) -> Settings:
    base = dict(
        llm_provider="auto",
        llm_model="",
        gemini_api_key="",
        gemini_model="gemini-3.5-flash-lite",
        gemini_base_url="",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        azure_openai_api_version="2024-02-15-preview",
        azure_openai_model="gpt-4o-mini",
        aws_access_key_id="",
        aws_secret_access_key="",
        aws_session_token="",
        aws_region="us-east-1",
        bedrock_model_id="",
    )
    base.update(kwargs)
    return Settings(**base)


def test_normalize_provider_aliases():
    assert normalize_provider("Google") == "gemini"
    assert normalize_provider("aws") == "bedrock"
    assert normalize_provider("azure-openai") == "azure"


def test_auto_prefers_gemini_when_key_present():
    settings = _settings(
        gemini_api_key="g-key",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="a-key",
    )
    assert detect_provider(settings) == "gemini"


def test_explicit_provider_wins():
    settings = _settings(
        llm_provider="azure",
        gemini_api_key="g-key",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="a-key",
    )
    assert detect_provider(settings) == "azure"


def test_llm_model_override():
    settings = _settings(llm_provider="gemini", gemini_api_key="g", llm_model="gemini-1.5-pro")
    assert resolve_model("gemini", settings) == "gemini-1.5-pro"


def test_transient_error_detection():
    assert is_transient_llm_error(RuntimeError("Error code: 503 - high demand"))
    assert not is_transient_llm_error(RuntimeError("Error code: 401 - invalid key"))


def test_model_candidates_keep_primary_first(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_FALLBACKS", "gemini-3.6-flash,gemini-3.8-flash")
    assert model_candidates("gemini-3.5-flash-lite")[0] == "gemini-3.5-flash-lite"
    assert "gemini-3.8-flash" in model_candidates("gemini-3.5-flash-lite")
