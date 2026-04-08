"""FastAPI dependency for per-plan API rate limiting with response headers."""

from __future__ import annotations

from fastapi import Request, Response
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.api.deps import AuthenticatedUser
from app.core.billing import RATE_WINDOW_SECONDS, get_rate_limit
from app.core.errors import RateLimitError
from app.core.rate_limiter import RateLimitResult, SlidingWindowRateLimiter


def _set_rate_limit_headers(response: Response, result: RateLimitResult) -> None:
    """Attach rate limit headers to the response."""
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset_after_seconds)
    if not result.allowed:
        response.headers["Retry-After"] = str(result.retry_after_seconds)


async def enforce_rate_limit(
    request: Request,
    response: Response,
    user: AuthenticatedUser,
) -> None:
    """Check rate limit for the authenticated user and set response headers.

    Requires ``request.app.state.redis`` to be set. Falls through
    silently when Redis is unavailable (fail-open).
    """
    redis: Redis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        return

    plan = user.plan
    limit = get_rate_limit(plan)
    limiter = SlidingWindowRateLimiter(redis)

    try:
        result = await limiter.check(
            identifier=f"user:{user.id}",
            limit=limit,
            window_seconds=RATE_WINDOW_SECONDS,
        )
    except (RedisConnectionError, OSError):
        return

    _set_rate_limit_headers(response, result)

    if not result.allowed:
        raise RateLimitError(
            f"Rate limit exceeded. Try again in {result.retry_after_seconds}s. "
            f"Plan '{plan}' allows {limit} requests per minute."
        )
