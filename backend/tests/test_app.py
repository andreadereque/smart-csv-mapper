import json
import logging
import sys
from pathlib import Path

import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient

from smart_csv_mapper.config import get_settings
from smart_csv_mapper.logging import (
    REQUEST_ID_HEADER,
    JsonFormatter,
    request_id_middleware,
    request_id_var,
)
from smart_csv_mapper.main import create_app


def test_healthz_reports_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_ok_when_the_model_answers(client: TestClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "llm": "fake"}


def test_readyz_is_503_when_the_model_is_down(client: TestClient) -> None:
    client.app.state.llm.ready = False  # type: ignore[attr-defined]
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "llm": "fake"}
    assert client.get("/healthz").status_code == 200


def test_request_id_is_generated_when_missing(client: TestClient) -> None:
    first = client.get("/healthz").headers[REQUEST_ID_HEADER]
    second = client.get("/healthz").headers[REQUEST_ID_HEADER]
    assert len(first) == 32
    assert first != second


def test_request_id_is_propagated_from_the_caller(client: TestClient) -> None:
    response = client.get("/healthz", headers={REQUEST_ID_HEADER: "abc-123"})
    assert response.headers[REQUEST_ID_HEADER] == "abc-123"


def test_create_app_reads_settings_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.sqlite"))
    create_app()
    assert logging.getLogger().level == logging.WARNING
    get_settings.cache_clear()


def _record(**kwargs: object) -> logging.LogRecord:
    record = logging.LogRecord("app", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    for key, value in kwargs.items():
        setattr(record, key, value)
    return record


def test_json_formatter_includes_message_and_request_id() -> None:
    token = request_id_var.set("req-1")
    try:
        line = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)
    assert line == {
        "level": "INFO",
        "logger": "app",
        "message": "hello world",
        "request_id": "req-1",
    }


def test_json_formatter_merges_extra_fields() -> None:
    line = json.loads(JsonFormatter().format(_record(extra_fields={"model": "qwen2.5:3b"})))
    assert line["model"] == "qwen2.5:3b"
    assert line["request_id"] == "-"


def test_json_formatter_includes_exception_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record(exc_info=sys.exc_info())
    line = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in line["exc_info"]


def test_request_id_does_not_leak_after_the_request() -> None:
    seen: list[str] = []

    async def call_next(_: Request) -> Response:
        seen.append(request_id_var.get())
        return Response()

    request = Request({"type": "http", "headers": [(b"x-request-id", b"req-9")]})
    # Drive the coroutine in *this* context (asyncio.run would use a copy and hide a leak).
    coroutine = request_id_middleware(request, call_next)
    with pytest.raises(StopIteration):
        coroutine.send(None)
    assert seen == ["req-9"]
    assert request_id_var.get() == "-"


def test_create_app_uses_the_provider_it_is_given(tmp_path: Path) -> None:
    from smart_csv_mapper.config import Settings
    from smart_csv_mapper.llm.fake import FakeProvider

    given = FakeProvider(model="injected")
    settings = Settings(llm_provider="ollama", audit_db_path=str(tmp_path / "a.sqlite"))
    app = create_app(settings, llm=given)
    assert app.state.llm is given
