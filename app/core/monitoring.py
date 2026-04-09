"""Observability setup: structured logging and optional Sentry integration."""

from __future__ import annotations

from fastapi import FastAPI, Request

from app.core import logging_config
from app.core.sentry_init import capture_sentry_exception, init_sentry

configure_logging = logging_config.configure_logging
get_logger = logging_config.get_logger


def setup_sentry() -> None:
    init_sentry()


def setup_monitoring(_app: FastAPI) -> None:
    configure_logging()
    setup_sentry()


def capture_exception_context(request: Request, exc: Exception) -> None:
    capture_sentry_exception(request, exc)
