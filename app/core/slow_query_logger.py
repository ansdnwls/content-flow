"""Helpers for logging slow Supabase queries with request correlation metadata."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.core.logging_config import get_logger
from app.core.request_id import get_current_user_id, get_request_id

DEFAULT_SLOW_QUERY_THRESHOLD_SECONDS = 0.5

logger = get_logger(__name__)


def log_slow_query(
    *,
    table: str,
    operation: str,
    duration_seconds: float,
    threshold_seconds: float = DEFAULT_SLOW_QUERY_THRESHOLD_SECONDS,
    user_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> bool:
    """Emit a warning when a Supabase query exceeds the slow-query threshold."""
    if duration_seconds <= threshold_seconds:
        return False

    logger.warning(
        "slow_supabase_query",
        table=table,
        operation=operation,
        duration_ms=round(duration_seconds * 1000, 2),
        threshold_ms=round(threshold_seconds * 1000, 2),
        user_id=user_id or get_current_user_id(),
        request_id=get_request_id(),
        **(extra or {}),
    )
    return True


class InstrumentedQuery:
    """Wrap a Supabase query builder and log slow `execute()` calls."""

    def __init__(
        self,
        query: Any,
        *,
        table_name: str,
        operation: str = "select",
        threshold_seconds: float = DEFAULT_SLOW_QUERY_THRESHOLD_SECONDS,
    ) -> None:
        self._query = query
        self._table_name = table_name
        self._operation = operation
        self._threshold_seconds = threshold_seconds

    def execute(self):
        started = perf_counter()
        result = self._query.execute()
        duration = perf_counter() - started
        log_slow_query(
            table=self._table_name,
            operation=self._operation,
            duration_seconds=duration,
            threshold_seconds=self._threshold_seconds,
        )
        return result

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._query, name)
        if not callable(target):
            return target

        def wrapper(*args, **kwargs):
            result = target(*args, **kwargs)
            if name in {"select", "insert", "upsert", "update", "delete"}:
                self._operation = name
            if result is self._query:
                return self
            return result

        return wrapper


class InstrumentedSupabaseClient:
    """Proxy Supabase client that instruments `.table(...).execute()` calls."""

    def __init__(
        self,
        client: Any,
        *,
        threshold_seconds: float = DEFAULT_SLOW_QUERY_THRESHOLD_SECONDS,
    ) -> None:
        self._client = client
        self._threshold_seconds = threshold_seconds

    def table(self, table_name: str) -> InstrumentedQuery:
        return InstrumentedQuery(
            self._client.table(table_name),
            table_name=table_name,
            threshold_seconds=self._threshold_seconds,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
