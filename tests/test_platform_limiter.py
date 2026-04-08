from __future__ import annotations

from datetime import UTC, datetime, timedelta

import fakeredis.aioredis

from app.core.platform_limiter import check_platform_limit


async def test_tiktok_limit_blocks_after_six_posts(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.platform_limiter.get_redis", fake_get_redis)

    for _ in range(6):
        decision = await check_platform_limit(
            "tiktok",
            "owner-1",
            "account-1",
            reserve=True,
        )
        assert decision.allowed is True

    blocked = await check_platform_limit("tiktok", "owner-1", "account-1")
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.next_available_at is not None


async def test_x_limit_returns_next_slot(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.platform_limiter.get_redis", fake_get_redis)

    base = datetime.now(UTC) - timedelta(hours=2, minutes=59)
    key = "contentflow:platform-limit:x_twitter:account-1"
    for index in range(300):
        timestamp = base + timedelta(seconds=index)
        await redis.zadd(key, {f"{index}:{index}:1": timestamp.timestamp()})

    decision = await check_platform_limit("x_twitter", "owner-1", "account-1")
    assert decision.allowed is False
    assert decision.next_available_at is not None
    assert decision.retry_after_seconds >= 0
