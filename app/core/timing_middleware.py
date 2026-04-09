"""Request timing middleware with response headers and slow-request warnings."""

from __future__ import annotations

from time import perf_counter

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import get_logger
from app.core.request_id import get_current_user_id

logger = get_logger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """Record request duration, expose X-Response-Time, and warn on slow requests."""

    def __init__(
        self,
        app,
        *,
        warning_threshold_seconds: float = 1.0,
        timer=perf_counter,
    ) -> None:
        super().__init__(app)
        self.warning_threshold_seconds = warning_threshold_seconds
        self.timer = timer

    async def dispatch(self, request: Request, call_next) -> Response:
        started = self.timer()
        response = await call_next(request)
        duration_seconds = self.timer() - started
        duration_ms = round(duration_seconds * 1000, 2)
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        if duration_seconds > self.warning_threshold_seconds:
            logger.warning(
                "slow_http_request",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                threshold_ms=round(self.warning_threshold_seconds * 1000, 2),
                user_id=getattr(request.state, "user_id", None) or get_current_user_id(),
            )

        return response
