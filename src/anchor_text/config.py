"""Configuration management for Anchor Text."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Configuration
    default_model: str = Field(
        default="gemini/gemini-3-pro-preview",
        alias="ANCHOR_TEXT_MODEL",
    )

    # API Keys (LiteLLM reads these automatically)
    # For Gemini, LiteLLM expects GEMINI_API_KEY
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    # Local LLM settings
    ollama_api_base: str = Field(
        default="http://localhost:11434",
        alias="OLLAMA_API_BASE",
    )

    # Processing settings
    max_chunk_tokens: int = Field(
        default=3000,
        alias="ANCHOR_TEXT_CHUNK_SIZE",
    )
    llm_temperature: float = Field(
        default=0.3,
        alias="ANCHOR_TEXT_TEMPERATURE",
    )
    max_retries: int = Field(
        default=3,
        alias="ANCHOR_TEXT_MAX_RETRIES",
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance, creating it if needed."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """Load settings from an optional specific .env file."""
    global _settings
    if env_file:
        _settings = Settings(_env_file=env_file)
    else:
        _settings = Settings()
    return _settings
