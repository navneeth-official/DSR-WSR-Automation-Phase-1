import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote_plus, urlparse, urlunparse

from dotenv import load_dotenv

from app.paths import REPO_ROOT

BACKEND_ENV = (
    REPO_ROOT / "DSR_WSR_AUTOMATION-Backend" / "backend" / "Jira-Automation" / ".env"
)

_env_loaded = False


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def load_app_env() -> None:
    """Load repo .env, then backend Jira-Automation .env for unset keys."""
    global _env_loaded
    if _env_loaded:
        return
    load_dotenv(REPO_ROOT / ".env")
    # Backend holds canonical DB credentials when repo root has no .env.
    load_dotenv(BACKEND_ENV, override=False)
    _env_loaded = True


def normalize_database_url(url: str) -> str:
    """Use psycopg2 (requirements.txt); SQLAlchemy 2.1+ defaults to psycopg v3 for postgresql://."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    return url


def resolve_database_url() -> str:
    """
    Build a SQLAlchemy URL from DATABASE_URL and/or POSTGRES_*.

    Fills a missing URL password from POSTGRES_PASSWORD (common when a shell
    DATABASE_URL has user/host only). URL-encodes the password for special chars.
    """
    load_app_env()
    user = _env("POSTGRES_USER", "postgres")
    password = _env("POSTGRES_PASSWORD", "postgres")
    host = _env("POSTGRES_HOST", "localhost")
    port = _env("POSTGRES_PORT", "5432")
    database = _env("POSTGRES_DB", "dsr_wsr_db")

    url = _env("DATABASE_URL")
    if not url:
        safe_password = quote_plus(password) if password else ""
        auth = f"{quote_plus(user)}:{safe_password}" if safe_password else quote_plus(user)
        url = f"postgresql://{auth}@{host}:{port}/{database}"
        return normalize_database_url(url)

    parsed = urlparse(url)
    scheme = parsed.scheme.replace("+psycopg2", "").replace("+psycopg", "")
    if scheme not in ("postgresql", "postgres"):
        return normalize_database_url(url)

    needs_password = not parsed.password and bool(password)
    if needs_password:
        hostname = parsed.hostname or host
        netloc_host = hostname
        parsed_port = parsed.port or (int(port) if port.isdigit() else None)
        if parsed_port:
            netloc_host = f"{netloc_host}:{parsed_port}"
        username = parsed.username or user
        netloc = f"{quote_plus(username)}:{quote_plus(password)}@{netloc_host}"
        path = parsed.path or f"/{database}"
        url = urlunparse(
            (
                "postgresql",
                netloc,
                path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

    return normalize_database_url(url)


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
    load_app_env()
    return Settings(
        database_url=resolve_database_url(),
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


load_app_env()