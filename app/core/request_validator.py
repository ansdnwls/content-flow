"""Request validation middleware — body size limits and suspicious header checks."""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB
UPLOAD_MAX_BODY_BYTES = 100 * 1024 * 1024  # 100 MB

_UPLOAD_PATHS = ("/api/v1/videos/", "/api/v1/posts/bulk")

_SCANNER_PATTERNS = re.compile(
    r"(sqlmap|nikto|nessus|dirbuster|gobuster|nuclei|wpscan|burpsuite)",
    re.IGNORECASE,
)


def _max_body_for_path(path: str) -> int:
    for prefix in _UPLOAD_PATHS:
        if path.startswith(prefix):
            return UPLOAD_MAX_BODY_BYTES
    return DEFAULT_MAX_BODY_BYTES


class RequestValidatorMiddleware(BaseHTTPMiddleware):
    """Reject oversized payloads and known scanner user-agents."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            max_body = _max_body_for_path(request.url.path)
            if int(content_length) > max_body:
                return JSONResponse(
                    {"detail": "Request body too large"},
                    status_code=413,
                )

        user_agent = request.headers.get("user-agent", "")
        if _SCANNER_PATTERNS.search(user_agent):
            return JSONResponse(
                {"detail": "Forbidden"},
                status_code=403,
            )

        return await call_next(request)
