"""Rate limiter stub — will use Redis in Week 2."""

from __future__ import annotations


async def check_rate_limit(user_id: str) -> None:
    """Check per-user rate limit. No-op until Redis is connected."""
    # TODO: Redis-backed sliding window rate limiter
    pass
