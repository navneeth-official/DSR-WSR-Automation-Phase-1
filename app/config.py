import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/dsr_wsr_db"

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_db: str = "dsr_wsr_db"

    # Which LLM backend to use: auto | gemini | azure | openai | bedrock
    llm_provider: str = "auto"
    # Optional model/deployment override for any provider
    llm_model: str = ""

    # Google Gemini (OpenAI-compatible API)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_base_url: str = ""

    # Standard OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_model: str = "gpt-4o-mini"

    # AWS Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = ""


def _settings_from_env() -> Settings:
    return Settings(
        database_url=_env(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/dsr_wsr_db",
        ),
        postgres_user=_env("POSTGRES_USER", "postgres"),
        postgres_password=_env("POSTGRES_PASSWORD", "postgres"),
        postgres_host=_env("POSTGRES_HOST", "localhost"),
        postgres_port=_env("POSTGRES_PORT", "5432"),
        postgres_db=_env("POSTGRES_DB", "dsr_wsr_db"),
        llm_provider=_env("LLM_PROVIDER", "auto") or "auto",
        llm_model=_env("LLM_MODEL"),
        gemini_api_key=_env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY"),
        gemini_model=_env("GEMINI_MODEL", "gemini-3.5-flash-lite")
        or "gemini-3.5-flash-lite",
        gemini_base_url=_env("GEMINI_BASE_URL"),
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_model=_env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
        azure_openai_endpoint=_env("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_key=_env("AZURE_OPENAI_API_KEY"),
        azure_openai_api_version=_env(
            "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
        )
        or "2024-02-15-preview",
        azure_openai_model=_env("AZURE_OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
        aws_access_key_id=_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_env("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=_env("AWS_SESSION_TOKEN"),
        aws_region=_env("AWS_REGION") or _env("AWS_DEFAULT_REGION", "us-east-1") or "us-east-1",
        bedrock_model_id=_env("BEDROCK_MODEL_ID") or _env("AWS_BEDROCK_MODEL_ID"),
    )


@lru_cache
def get_settings() -> Settings:
    return _settings_from_env()


def llm_configured(settings: Settings | None = None) -> bool:
    """True when at least one supported LLM provider has credentials."""
    from app.services.llm_client import detect_provider, provider_configured

    s = settings or get_settings()
    provider = detect_provider(s)
    if provider is None:
        return False
    return provider_configured(provider, s)
