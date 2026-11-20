"""Pick the provider from the settings."""

from smart_csv_mapper.config import Settings
from smart_csv_mapper.llm.base import LLMProvider
from smart_csv_mapper.llm.fake import FakeProvider
from smart_csv_mapper.llm.ollama import OllamaProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(settings.ollama_url, settings.llm_model)
    if settings.llm_provider == "fake":
        return FakeProvider()
    raise ValueError(f"LLM provider {settings.llm_provider!r} is not available yet (PR 12)")
