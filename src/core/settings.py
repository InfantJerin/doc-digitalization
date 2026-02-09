"""Application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Document Digitalization Platform"
    app_version: str = "2.0.0"
    environment: str = "dev"
    log_level: str = "INFO"

    llm_provider: str = "anthropic"
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: int = 120
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    agent_model: str = "claude-sonnet-4-20250514"
    agent_permission_mode: str = "bypassPermissions"

    dms_base_url: str = "http://localhost:8080"
    dms_api_key: str = ""

    database_url: str = "sqlite+aiosqlite:///./doc_digitalization.db"

    extractions_root: Path = Field(default_factory=lambda: Path("/tmp/extractions"))
    skills_dir: Path = Field(default_factory=lambda: Path("skills"))
    config_dir: Path = Field(default_factory=lambda: Path("config/pipelines"))

    default_max_turns: int = 120
    default_max_budget_usd: float = 5.0
    covenant_max_turns: int = 50
    covenant_max_budget_usd: float = 2.0
    credit_agreement_max_turns: int = 150
    credit_agreement_max_budget_usd: float = 8.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
