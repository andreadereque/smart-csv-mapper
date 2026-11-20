"""Runtime configuration, read from environment variables (and `.env` in development)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["ollama", "claude", "fake"] = "ollama"
    llm_model: str = "qwen2.5:3b"
    ollama_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    redis_url: str = ""
    max_upload_mb: int = 10
    max_rows: int = 50_000
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
