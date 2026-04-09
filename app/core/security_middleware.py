"""Security middleware: response headers and request validation."""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


_BASE_SECURITY_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

_PROD_CSP = "default-src 'self'"

_DEV_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self'"
)


def _is_dev_mode() -> bool:
    """Detect development mode without depending on Settings model."""
    env = os.getenv("CONTENTFLOW_ENV", "").lower()
    if env in ("development", "dev", "local"):
        return True
    # Fallback: if running on localhost, assume dev
    return os.getenv("UVICORN_HOST", "127.0.0.1") in ("127.0.0.1", "localhost", "0.0.0.0")


_CSP = _DEV_CSP if _is_dev_mode() else _PROD_CSP


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers into every HTTP response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        for header, value in _BASE_SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        return response