"""FastAPI dependency for per-plan API rate limiting with response headers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request, Response
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.errors import RateLimitError
from app.core.rate_limiter_v2 import (
    SlidingWindowRateLimiterV2,
    get_rate_limit_policies,
)

if TYPE_CHECKING:
    from app.api.deps import AuthenticatedUser


def _set_rate_limit_headers(response: Response, result) -> dict[str, str]:
    """Attach rate limit headers to the response."""
    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(result.reset_after_seconds),
    }
    for key, value in headers.items():
        response.headers[key] = value
    if result.warning:
        headers["X-RateLimit-Warning"] = result.warning
        response.headers["X-RateLimit-Warning"] = result.warning
    if not result.allowed:
        headers["Retry-After"] = str(result.retry_after_seconds)
        response.headers["Retry-After"] = str(result.retry_after_seconds)
    return headers


async def enforce_rate_limit(
    request: Request,
    response: Response,
    user: AuthenticatedUser,
) -> None:
    """Check rate limits for the authenticated user and set response headers."""
    redis: Redis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        return

    limiter = SlidingWindowRateLimiterV2(redis)
    policies = get_rate_limit_policies(
        user,
        method=request.method,
        path=request.url.path,
    )

    try:
        results = []
        for policy in policies:
            result = await limiter.check(
                identifier=f"user:{user.id}",
                limit=policy.limit,
                window_seconds=policy.window_seconds,
                scope=policy.scope,
            )
            results.append(result)
            if not result.allowed:
                headers = _set_rate_limit_headers(response, result)
                raise RateLimitError(
                    (
                        f"Rate limit exceeded for {result.scope}. "
                        f"Try again in {result.retry_after_seconds}s."
                    ),
                    headers=headers,
                )
    except (RedisConnectionError, OSError):
        return

    display = min(results, key=lambda item: item.limit)
    _set_rate_limit_headers(response, display)
