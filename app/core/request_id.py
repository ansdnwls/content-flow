"""Request ID middleware and context propagation helpers."""

from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def get_request_id() -> str | None:
    """Return the current request ID if one is bound to the context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> Token:
    """Bind a request ID to the current async context."""
    return _request_id_var.set(request_id)


def clear_request_id(token: Token) -> None:
    """Restore the previous request ID context."""
    _request_id_var.reset(token)


def get_current_user_id() -> str | None:
    """Return the current authenticated user ID from context when available."""
    return _user_id_var.get()


def set_current_user_id(user_id: str | None) -> Token:
    """Bind the current authenticated user ID to the async context."""
    return _user_id_var.set(user_id)


def clear_current_user_id(token: Token) -> None:
    """Restore the previous user ID context."""
    _user_id_var.reset(token)


class RequestIdMiddleware:
    """Attach a request ID to request state, contextvars, and response headers."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get("X-Request-ID") or str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        request_token = set_request_id(request_id)
        user_token = set_current_user_id(None)

        async def send_with_request_id(message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            clear_current_user_id(user_token)
            clear_request_id(request_token)
