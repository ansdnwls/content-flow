"""Application middleware for request logging and error tracking."""

from __future__ import annotations

from time import perf_counter

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import record_http_request
from app.core.monitoring import capture_exception_context, get_logger
from app.core.request_id import get_request_id

logger = get_logger(__name__)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = perf_counter()
        response = await call_next(request)
        duration = perf_counter() - started
        path = _route_path(request)
        record_http_request(request.method, path, response.status_code, duration)
        logger.info(
            "http_request",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            user_id=getattr(request.state, "user_id", None),
        )
        return response


class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            capture_exception_context(request, exc)
            logger.exception(
                "unhandled_exception",
                path=request.url.path,
                method=request.method,
                user_id=getattr(request.state, "user_id", None),
                api_key_prefix=getattr(request.state, "api_key_prefix", None),
                endpoint=request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": get_request_id() or ""},
            )
