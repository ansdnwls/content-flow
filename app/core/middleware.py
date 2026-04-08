"""Application middleware for request IDs, logging, and error tracking."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import record_http_request
from app.core.monitoring import capture_exception_context, get_logger

logger = get_logger(__name__)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


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
            request_id=getattr(request.state, "request_id", ""),
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
                request_id=getattr(request.state, "request_id", ""),
                user_id=getattr(request.state, "user_id", None),
                api_key_prefix=getattr(request.state, "api_key_prefix", None),
                endpoint=request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": getattr(request.state, "request_id", "")},
            )
