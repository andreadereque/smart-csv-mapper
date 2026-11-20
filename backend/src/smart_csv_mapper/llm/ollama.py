"""Ollama, running locally: free, and the data never leaves the machine."""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable

import httpx

from smart_csv_mapper.llm.base import JsonSchema, LLMError, LLMResponse

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_s: float = 120.0,
        max_retries: int = 2,
        backoff_s: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._max_retries = max_retries
        self._backoff = backoff_s
        self._transport = transport
        self._sleep = sleep

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        )

    async def complete_json(self, prompt: str, schema: JsonSchema) -> LLMResponse:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,  # structured outputs: Ollama constrains the JSON to the schema
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": prompt}],
        }
        started = time.perf_counter()
        payload = await self._post_with_retries("/api/chat", body)
        latency_ms = int((time.perf_counter() - started) * 1000)
        data = _parse_content(payload)
        response = LLMResponse(
            data=data,
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=_int_or_none(payload.get("prompt_eval_count")),
            output_tokens=_int_or_none(payload.get("eval_count")),
        )
        logger.info(
            "llm_call",
            extra={
                "extra_fields": {
                    "provider": self.name,
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                }
            },
        )
        return response

    async def _post_with_retries(self, path: str, body: dict[str, object]) -> dict[str, object]:
        attempt = 0
        while True:
            try:
                async with self._client() as client:
                    response = await client.post(path, json=body)
                if response.status_code < 500:
                    response.raise_for_status()
                    result: dict[str, object] = response.json()
                    return result
                problem = LLMError("unavailable", f"Ollama returned {response.status_code}")
            except httpx.TimeoutException:
                problem = LLMError("timeout", "Ollama did not answer in time")
            except httpx.TransportError as error:
                problem = LLMError("unavailable", f"Cannot reach Ollama: {error}")
            except httpx.HTTPStatusError as error:
                raise LLMError("unavailable", f"Ollama rejected the request: {error}") from None
            if attempt == self._max_retries:
                raise problem
            await self._sleep(self._backoff * 2**attempt)
            attempt += 1

    async def is_ready(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get("/api/tags", timeout=2.0)
        except httpx.HTTPError:
            return False
        return response.status_code == 200


def _parse_content(payload: dict[str, object]) -> dict[str, object]:
    message = payload.get("message")
    content = ""
    if isinstance(message, dict):
        content = str(message.get("content", ""))
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise LLMError("invalid_json", "The model did not return valid JSON") from None
    if not isinstance(data, dict):
        raise LLMError("invalid_json", "The model returned JSON that is not an object")
    return data


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None
