"""Structured logging configuration built on structlog."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

import structlog

from app.config import get_settings
from app.core.request_id import get_request_id


def _add_request_id(_logger, _method_name: str, event_dict: dict) -> dict:
    """Attach the current request ID from context when available."""
    request_id = get_request_id()
    if request_id and "request_id" not in event_dict:
        event_dict["request_id"] = request_id
    return event_dict


def _shared_processors() -> list:
    return [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def configure_logging(*, stream: TextIO | None = None, renderer: str = "auto") -> None:
    """Configure structlog for JSON production logs and colored local logs."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    target_stream = stream or sys.stdout

    use_json = renderer == "json" or (
        renderer == "auto"
        and settings.app_env.lower() not in {"development", "dev", "local", "test", "testing"}
    )

    logging.basicConfig(level=level, stream=target_stream, format="%(message)s", force=True)
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            *_shared_processors(),
            (
                structlog.processors.JSONRenderer()
                if use_json
                else structlog.dev.ConsoleRenderer(colors=True)
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=target_stream),
        cache_logger_on_first_use=False,
    )


class _LoggerProxy:
    """Resolve a fresh structlog logger on each call so reconfiguration is respected."""

    def __init__(self, name: str) -> None:
        self.name = name

    def _logger(self):
        return structlog.get_logger(self.name).bind(logger=self.name)

    def info(self, event: str, **fields) -> None:
        self._logger().info(event, **fields)

    def warning(self, event: str, **fields) -> None:
        self._logger().warning(event, **fields)

    def error(self, event: str, **fields) -> None:
        self._logger().error(event, **fields)

    def exception(self, event: str, **fields) -> None:
        self._logger().exception(event, **fields)


def get_logger(name: str) -> _LoggerProxy:
    """Return a lazily resolved structlog logger for the given module."""
    return _LoggerProxy(name)
