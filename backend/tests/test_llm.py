import json
import logging
from typing import Any

import httpx
import pytest

from smart_csv_mapper.config import Settings
from smart_csv_mapper.llm.base import LLMError
from smart_csv_mapper.llm.factory import build_provider
from smart_csv_mapper.llm.fake import FakeProvider
from smart_csv_mapper.llm.ollama import OllamaProvider

SCHEMA = {"type": "object", "properties": {"email_column": {"type": "string"}}}
Handler = Any


def ollama_reply(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={"message": {"content": content}, "prompt_eval_count": 45, "eval_count": 10},
    )


class Recorder:
    """Ollama stand-in: answers from a script and remembers each request."""

    def __init__(self, *replies: httpx.Response | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def provider(recorder: Recorder, sleeps: list[float] | None = None) -> OllamaProvider:
    async def fake_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return OllamaProvider(
        "http://ollama:11434/",
        "qwen2.5:3b",
        transport=httpx.MockTransport(recorder),
        sleep=fake_sleep,
    )


async def test_sends_schema_and_temperature_zero_and_parses_the_answer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    recorder = Recorder(ollama_reply('{"email_column": "Correo"}'))
    caplog.set_level(logging.INFO)
    response = await provider(recorder).complete_json("Which column?", SCHEMA)
    assert response.data == {"email_column": "Correo"}
    assert response.model == "qwen2.5:3b"
    assert (response.input_tokens, response.output_tokens) == (45, 10)
    sent = json.loads(recorder.requests[0].content)
    assert str(recorder.requests[0].url) == "http://ollama:11434/api/chat"
    assert sent["format"] == SCHEMA
    assert sent["options"] == {"temperature": 0}
    assert sent["stream"] is False
    assert sent["messages"] == [{"role": "user", "content": "Which column?"}]
    log = next(r for r in caplog.records if r.getMessage() == "llm_call")
    assert log.extra_fields["model"] == "qwen2.5:3b"  # type: ignore[attr-defined]


async def test_retries_server_errors_with_exponential_backoff() -> None:
    sleeps: list[float] = []
    recorder = Recorder(
        httpx.Response(500), httpx.ConnectError("refused"), ollama_reply('{"a": 1}')
    )
    response = await provider(recorder, sleeps).complete_json("p", SCHEMA)
    assert response.data == {"a": 1}
    assert sleeps == [0.5, 1.0]
    assert len(recorder.requests) == 3


async def test_gives_up_after_the_last_retry_with_the_last_error_kind() -> None:
    recorder = Recorder(httpx.Response(503), httpx.Response(503), httpx.ReadTimeout("slow"))
    with pytest.raises(LLMError) as error:
        await provider(recorder).complete_json("p", SCHEMA)
    assert error.value.kind == "timeout"
    assert len(recorder.requests) == 3


async def test_client_errors_are_not_retried() -> None:
    recorder = Recorder(httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(LLMError) as error:
        await provider(recorder).complete_json("p", SCHEMA)
    assert error.value.kind == "unavailable"
    assert "rejected" in str(error.value)
    assert len(recorder.requests) == 1


async def test_unreachable_ollama_is_unavailable() -> None:
    recorder = Recorder(*[httpx.ConnectError("refused")] * 3)
    with pytest.raises(LLMError) as error:
        await provider(recorder).complete_json("p", SCHEMA)
    assert error.value.kind == "unavailable"


@pytest.mark.parametrize(
    "payload",
    [
        {"message": {"content": "not json"}},
        {"message": {"content": "[1, 2]"}},
        {"message": {"content": '"just text"'}},
        {"message": {"content": "42"}},
        {"message": "weird"},
        {},
    ],
)
async def test_invalid_answers_raise_invalid_json(payload: dict[str, Any]) -> None:
    recorder = Recorder(httpx.Response(200, json=payload))
    with pytest.raises(LLMError) as error:
        await provider(recorder).complete_json("p", SCHEMA)
    assert error.value.kind == "invalid_json"


async def test_is_ready_checks_the_tags_endpoint() -> None:
    recorder = Recorder(httpx.Response(200, json={"models": []}))
    assert await provider(recorder).is_ready() is True
    assert recorder.requests[0].url.path == "/api/tags"


async def test_is_not_ready_on_error_status_or_connection_failure() -> None:
    assert await provider(Recorder(httpx.Response(500))).is_ready() is False
    assert await provider(Recorder(httpx.Response(404))).is_ready() is False
    assert await provider(Recorder(httpx.ConnectError("refused"))).is_ready() is False


async def test_fake_provider_replays_answers_and_errors_in_order() -> None:
    fake = FakeProvider([{"a": 1}, LLMError("timeout", "slow")])
    assert (await fake.complete_json("first", SCHEMA)).data == {"a": 1}
    with pytest.raises(LLMError):
        await fake.complete_json("second", SCHEMA)
    with pytest.raises(AssertionError, match="ran out"):
        await fake.complete_json("third", SCHEMA)
    assert fake.prompts == ["first", "second", "third"]
    assert await fake.is_ready() is True


def test_factory_builds_the_configured_provider() -> None:
    ollama = build_provider(Settings(llm_provider="ollama", llm_model="llama3.2:3b"))
    assert isinstance(ollama, OllamaProvider)
    assert ollama.model == "llama3.2:3b"
    assert isinstance(build_provider(Settings(llm_provider="fake")), FakeProvider)
    with pytest.raises(ValueError, match="PR 12"):
        build_provider(Settings(llm_provider="claude"))


async def test_missing_token_counts_are_none() -> None:
    recorder = Recorder(httpx.Response(200, json={"message": {"content": "{}"}}))
    response = await provider(recorder).complete_json("p", SCHEMA)
    assert (response.input_tokens, response.output_tokens) == (None, None)
