"""Observability setup: structured logging and optional Sentry integration."""

from __future__ import annotations

from fastapi import FastAPI, Request

from app.config import get_settings
from app.core import logging_config

try:
    import sentry_sdk
except ImportError:  # pragma: no cover - optional dependency
    sentry_sdk = None

try:  # pragma: no cover - optional dependency
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except Exception:  # pragma: no cover - optional dependency
    FastApiIntegration = None


configure_logging = logging_config.configure_logging
get_logger = logging_config.get_logger


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
