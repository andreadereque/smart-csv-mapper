"""A scripted provider for tests: returns queued answers and records every prompt."""

from typing import Any

from smart_csv_mapper.llm.base import JsonSchema, LLMError, LLMResponse


class FakeProvider:
    name = "fake"

    def __init__(
        self, answers: list[dict[str, Any] | LLMError] | None = None, model: str = "fake-model"
    ) -> None:
        self.model = model
        self.answers: list[dict[str, Any] | LLMError] = list(answers or [])
        self.prompts: list[str] = []
        self.ready = True

    async def complete_json(self, prompt: str, schema: JsonSchema) -> LLMResponse:
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError("FakeProvider ran out of scripted answers")
        answer = self.answers.pop(0)
        if isinstance(answer, LLMError):
            raise answer
        return LLMResponse(data=answer, model=self.model, latency_ms=1)

    async def is_ready(self) -> bool:
        return self.ready
