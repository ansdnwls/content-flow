import asyncio

import fakeredis.aioredis
import pytest

from app.core.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_sliding_window_blocks_after_limit() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = SlidingWindowRateLimiter(redis)

    first = await limiter.check(identifier="user:1", limit=2, window_seconds=60)
    second = await limiter.check(identifier="user:1", limit=2, window_seconds=60)
    third = await limiter.check(identifier="user:1", limit=2, window_seconds=60)

    assert first.allowed is True
    assert second.allowed is True
    assert second.remaining == 0
    assert third.allowed is False
    assert third.retry_after_seconds >= 1


@pytest.mark.asyncio
async def test_sliding_window_resets_after_window() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = SlidingWindowRateLimiter(redis)

    await limiter.check(identifier="user:2", limit=1, window_seconds=1)
    blocked = await limiter.check(identifier="user:2", limit=1, window_seconds=1)
    await asyncio.sleep(1.1)
    allowed = await limiter.check(identifier="user:2", limit=1, window_seconds=1)

    assert blocked.allowed is False
    assert allowed.allowed is True
