from __future__ import annotations

import json
import warnings
from io import StringIO
from types import SimpleNamespace

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.logging_config import configure_logging, get_logger
from app.core.request_id import (
    RequestIdMiddleware,
    clear_current_user_id,
    clear_request_id,
    set_current_user_id,
    set_request_id,
)
from app.core.slow_query_logger import InstrumentedQuery, log_slow_query
from app.core.timing_middleware import TimingMiddleware


def _parse_json_logs(buffer: StringIO) -> list[dict]:
    return [
        json.loads(line)
        for line in buffer.getvalue().splitlines()
        if line.strip().startswith("{")
    ]


def test_structlog_console_renderer_emits_no_format_exc_info_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = StringIO()
    settings = Settings(APP_ENV="development", LOG_LEVEL="INFO")
    monkeypatch.setattr("app.core.logging_config.get_settings", lambda: settings)
    configure_logging(stream=buffer, renderer="console")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            structlog.get_logger("test").exception("console_exception")

    assert not any(
        "Remove format_exc_info from your processor chain" in str(item.message)
        for item in caught
    )


def test_slow_query_logging_records_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.slow_query_logger as slow_query_logger

    timings = iter([0.0, 0.75])
    captured: list[dict] = []
    request_token = set_request_id("req-slow")
    user_token = set_current_user_id("user-123")

    class FakeQuery:
        def select(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(data=[{"id": "user-123"}])

    monkeypatch.setattr(slow_query_logger, "perf_counter", lambda: next(timings))
    monkeypatch.setattr(
        slow_query_logger.logger,
        "warning",
        lambda event, **fields: captured.append({"event": event, **fields}),
    )

    try:
        InstrumentedQuery(FakeQuery(), table_name="users").select("*").execute()
    finally:
        clear_request_id(request_token)
        clear_current_user_id(user_token)

    assert captured == [
        {
            "event": "slow_supabase_query",
            "table": "users",
            "operation": "select",
            "duration_ms": 750.0,
            "threshold_ms": 500.0,
            "user_id": "user-123",
            "request_id": "req-slow",
        }
    ]


def test_timing_middleware_adds_response_time_header() -> None:
    app = FastAPI()
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/ok")

    assert response.status_code == 200
    assert response.headers["X-Response-Time"].endswith("ms")


def test_timing_middleware_warns_on_requests_over_one_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    timings = iter([0.0, 1.25])
    captured: list[dict] = []
    app.add_middleware(
        TimingMiddleware,
        timer=lambda: next(timings),
        warning_threshold_seconds=1.0,
    )
    app.add_middleware(RequestIdMiddleware)

    @app.get("/slow")
    async def slow():
        return {"ok": True}

    monkeypatch.setattr(
        "app.core.timing_middleware.logger.warning",
        lambda event, **fields: captured.append({"event": event, **fields}),
    )

    with TestClient(app) as client:
        response = client.get("/slow")

    assert response.status_code == 200
    assert captured == [
        {
            "event": "slow_http_request",
            "method": "GET",
            "path": "/slow",
            "duration_ms": 1250.0,
            "threshold_ms": 1000.0,
            "user_id": None,
        }
    ]


def test_sentry_init_skips_gracefully_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.sentry_init as sentry_init

    monkeypatch.setattr(
        sentry_init,
        "get_settings",
        lambda: Settings(APP_ENV="test", SENTRY_DSN=None),
    )
    monkeypatch.setattr(sentry_init, "sentry_sdk", object())

    assert sentry_init.init_sentry() is False


def test_sentry_init_calls_sdk_when_dsn_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.sentry_init as sentry_init

    captured: dict = {}

    class FakeSentry:
        def init(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        sentry_init,
        "get_settings",
        lambda: Settings(
            APP_ENV="production",
            SENTRY_DSN="https://example@sentry.io/1",
            SENTRY_TRACES_SAMPLE_RATE=0.25,
        ),
    )
    monkeypatch.setattr(sentry_init, "sentry_sdk", FakeSentry())
    monkeypatch.setattr(sentry_init, "FastApiIntegration", lambda: "fastapi-integration")

    assert sentry_init.init_sentry() is True
    assert captured["dsn"] == "https://example@sentry.io/1"
    assert captured["environment"] == "production"
    assert captured["traces_sample_rate"] == 0.25
    assert captured["integrations"] == ["fastapi-integration"]


def test_main_middleware_order_places_request_id_before_timing_and_logging() -> None:
    from app.main import app

    names = [middleware.cls.__name__ for middleware in app.user_middleware]

    assert names.index("RequestIdMiddleware") < names.index("TimingMiddleware")
    assert names.index("TimingMiddleware") < names.index("ResponseCacheInvalidationMiddleware")
    assert names.index("ResponseCacheInvalidationMiddleware") < names.index("LoggingMiddleware")


def test_correlation_id_propagates_across_loggers(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = StringIO()
    settings = Settings(APP_ENV="production", LOG_LEVEL="INFO")
    monkeypatch.setattr("app.core.logging_config.get_settings", lambda: settings)
    configure_logging(stream=buffer, renderer="json")

    app = FastAPI()
    app.add_middleware(TimingMiddleware, warning_threshold_seconds=5.0)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/chain")
    async def chain():
        get_logger(__name__).info("route_log")
        log_slow_query(
            table="users",
            operation="select",
            duration_seconds=0.6,
            user_id="user-chain",
        )
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/chain", headers={"X-Request-ID": "corr-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "corr-123"

    logs = _parse_json_logs(buffer)
    route_log = next(entry for entry in logs if entry["event"] == "route_log")
    slow_log = next(entry for entry in logs if entry["event"] == "slow_supabase_query")

    assert route_log["request_id"] == "corr-123"
    assert slow_log["request_id"] == "corr-123"
    assert slow_log["user_id"] == "user-chain"
