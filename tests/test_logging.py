from __future__ import annotations

import json
from io import StringIO
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging_config import configure_logging
from app.core.middleware import ErrorTrackingMiddleware, LoggingMiddleware
from app.core.request_id import RequestIdMiddleware, get_request_id


@pytest.fixture()
def log_buffer(monkeypatch) -> StringIO:
    from app.config import Settings

    buffer = StringIO()
    settings = Settings(
        APP_ENV="production",
        LOG_LEVEL="INFO",
    )
    monkeypatch.setattr("app.core.logging_config.get_settings", lambda: settings)
    configure_logging(stream=buffer, renderer="json")
    return buffer


@pytest.fixture()
def logging_app(monkeypatch, log_buffer: StringIO) -> FastAPI:
    app = FastAPI()

    monkeypatch.setattr(
        "app.core.middleware.record_http_request",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.core.middleware.capture_exception_context",
        lambda *args, **kwargs: None,
    )

    app.add_middleware(ErrorTrackingMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/context")
    async def context_route():
        return {"request_id": get_request_id()}

    @app.get("/ok")
    async def ok_route():
        return {"ok": True}

    @app.get("/boom")
    async def boom_route():
        raise RuntimeError("boom")

    return app


def _parse_log_lines(buffer: StringIO) -> list[dict]:
    lines = [
        line.strip()
        for line in buffer.getvalue().splitlines()
        if line.strip().startswith("{")
    ]
    return [json.loads(line) for line in lines]


def test_request_id_is_generated_automatically(logging_app: FastAPI) -> None:
    with TestClient(logging_app) as client:
        response = client.get("/context")

    assert response.status_code == 200
    request_id = response.json()["request_id"]
    assert request_id == response.headers["X-Request-ID"]
    UUID(request_id)


def test_existing_request_id_is_reused(logging_app: FastAPI) -> None:
    with TestClient(logging_app) as client:
        response = client.get("/context", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "req-123"
    assert response.headers["X-Request-ID"] == "req-123"


def test_response_header_contains_request_id(logging_app: FastAPI) -> None:
    with TestClient(logging_app) as client:
        response = client.get("/ok")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_structured_logs_render_as_json(
    logging_app: FastAPI,
    log_buffer: StringIO,
) -> None:
    with TestClient(logging_app) as client:
        response = client.get("/ok", headers={"X-Request-ID": "req-json"})

    assert response.status_code == 200
    http_log = next(
        entry for entry in _parse_log_lines(log_buffer)
        if entry["event"] == "http_request"
    )
    assert http_log["request_id"] == "req-json"
    assert http_log["method"] == "GET"
    assert http_log["status_code"] == 200
    assert http_log["timestamp"]


def test_error_logs_include_request_id(
    logging_app: FastAPI,
    log_buffer: StringIO,
) -> None:
    with TestClient(logging_app, raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"X-Request-ID": "req-error"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "req-error"

    error_log = next(
        entry for entry in _parse_log_lines(log_buffer)
        if entry["event"] == "unhandled_exception"
    )
    assert error_log["request_id"] == "req-error"
    assert error_log["path"] == "/boom"
