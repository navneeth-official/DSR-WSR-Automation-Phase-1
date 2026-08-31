import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/dsr_wsr_db",
    )

    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    postgres_db: str = os.getenv("POSTGRES_DB", "dsr_wsr_db")

    # Google AI Studio Gemini (primary when GEMINI_API_KEY is set)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    gemini_vision_model: str = os.getenv(
        "GEMINI_VISION_MODEL", "gemini-3.5-flash-lite"
    )
    llm_provider: str = os.getenv("LLM_PROVIDER", "auto")
    wsr_llm_max_calls_per_minute: int = int(
        os.getenv("WSR_LLM_MAX_CALLS_PER_MINUTE", "10")
    )

    # Standard OpenAI (optional fallback)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "")

    # Azure OpenAI (optional fallback)
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_api_version: str = os.getenv(
        "AZURE_OPENAI_API_VERSION", "2024-02-15-preview"
    )
    azure_openai_model: str = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini")
    azure_openai_vision_model: str = os.getenv("AZURE_OPENAI_VISION_MODEL", "")

    # Microsoft Entra app (personal OneDrive upload via Graph — delegated MSAL)
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_authority: str = os.getenv("AZURE_AUTHORITY", "")
    onedrive_upload_folder: str = os.getenv("ONEDRIVE_UPLOAD_FOLDER", "WSR")
    onedrive_upload_enabled: bool = os.getenv(
        "ONEDRIVE_UPLOAD_ENABLED", ""
    ).lower() in ("1", "true", "yes")

    # Cloud upload provider: google_drive | onedrive | (empty = use *_UPLOAD_ENABLED flags)
    cloud_upload_provider: str = os.getenv("CLOUD_UPLOAD_PROVIDER", "")

    # Google Drive upload via Drive API v3 (OAuth desktop client)
    google_drive_upload_folder: str = os.getenv("GOOGLE_DRIVE_UPLOAD_FOLDER", "WSR")
    google_drive_client_secret_file: str = os.getenv(
        "GOOGLE_DRIVE_CLIENT_SECRET_FILE", ""
    )
    google_drive_upload_enabled: bool = os.getenv(
        "GOOGLE_DRIVE_UPLOAD_ENABLED", ""
    ).lower() in ("1", "true", "yes")

    # Slide preview export: auto | com | libreoffice
    ppt_render_backend: str = os.getenv("PPT_RENDER_BACKEND", "auto")
    libreoffice_path: str = os.getenv("LIBREOFFICE_PATH", "")
    pdftoppm_path: str = os.getenv("PDFTOPPM_PATH", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_llm_provider(settings: Settings | None = None) -> str:
    """Return active LLM provider: gemini, azure, openai, or none."""
    s = settings or get_settings()
    preference = (s.llm_provider or "auto").lower()

    has_gemini = bool(s.gemini_api_key)
    has_azure = bool(s.azure_openai_endpoint and s.azure_openai_api_key)
    has_openai = bool(s.openai_api_key)

    if preference == "gemini":
        return "gemini" if has_gemini else "none"
    if preference == "azure":
        return "azure" if has_azure else "none"
    if preference == "openai":
        return "openai" if has_openai else "none"

    # auto: prefer Gemini, then Azure, then OpenAI
    if has_gemini:
        return "gemini"
    if has_azure:
        return "azure"
    if has_openai:
        return "openai"
    return "none"


def llm_configured(settings: Settings | None = None) -> bool:
    """True when any supported LLM provider is configured."""
    return resolve_llm_provider(settings) != "none"
