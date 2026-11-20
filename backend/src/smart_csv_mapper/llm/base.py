"""The one interface every model provider implements (ADR-004)."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

JsonSchema = dict[str, Any]
ErrorKind = Literal["unavailable", "timeout", "invalid_json"]


@dataclass(frozen=True)
class LLMResponse:
    data: dict[str, Any]
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMError(Exception):
    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class LLMProvider(Protocol):
    name: str
    model: str

    async def complete_json(self, prompt: str, schema: JsonSchema) -> LLMResponse:
        """Return a JSON object that the model was asked to shape like `schema`."""
        ...

    async def is_ready(self) -> bool:
        """Cheap check used by /readyz."""
        ...
