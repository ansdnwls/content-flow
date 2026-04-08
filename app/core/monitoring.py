"""Observability setup: structured logging and optional Sentry integration."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from fastapi import FastAPI, Request

from app.config import get_settings

try:
    import structlog
except ImportError:  # pragma: no cover - optional dependency
    structlog = None

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - optional dependency
    sentry_sdk = None

try:  # pragma: no cover - optional dependency
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except Exception:  # pragma: no cover - optional dependency
    FastApiIntegration = None


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "event": record.getMessage(),
            "level": record.levelname.lower(),
            "logger": record.name,
        }
        extra = getattr(record, "structured", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


class _LoggerProxy:
    def __init__(self, logger: Any) -> None:
        self._logger = logger

    def info(self, event: str, **fields: Any) -> None:
        self._emit("info", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit("warning", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit("error", event, **fields)

    def exception(self, event: str, **fields: Any) -> None:
        self._emit("exception", event, **fields)

    def _emit(self, level: str, event: str, **fields: Any) -> None:
        if structlog is not None and hasattr(self._logger, level):
            getattr(self._logger, level)(event, **fields)
            return
        log_method = getattr(self._logger, "exception" if level == "exception" else level)
        log_method(event, extra={"structured": fields})


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s", force=True)

    if structlog is not None and settings.structured_logging_enabled:
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        return

    root = logging.getLogger()
    for handler in root.handlers:
        handler.setFormatter(_JsonFormatter())


def setup_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn or sentry_sdk is None:
        return

    integrations = [FastApiIntegration()] if FastApiIntegration is not None else []
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=integrations,
    )


def setup_monitoring(_app: FastAPI) -> None:
    configure_logging()
    setup_sentry()


def get_logger(name: str) -> _LoggerProxy:
    if structlog is not None:
        return _LoggerProxy(structlog.get_logger(name))
    return _LoggerProxy(logging.getLogger(name))


def capture_exception_context(request: Request, exc: Exception) -> None:
    if sentry_sdk is None or get_settings().sentry_dsn is None:
        return

    with sentry_sdk.push_scope() as scope:
        user_id = getattr(request.state, "user_id", None)
        api_key_prefix = getattr(request.state, "api_key_prefix", None)
        endpoint = request.url.path

        if user_id:
            scope.user = {"id": user_id}
            scope.set_tag("user_id", user_id)
        if api_key_prefix:
            scope.set_tag("api_key_prefix", api_key_prefix)
        scope.set_tag("endpoint", endpoint)
        scope.set_tag("request_id", getattr(request.state, "request_id", ""))
        sentry_sdk.capture_exception(exc)
