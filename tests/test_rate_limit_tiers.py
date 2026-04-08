from __future__ import annotations

from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from fastapi import Response

from app.api.deps import AuthenticatedUser
from app.core.errors import RateLimitError
from app.core.rate_limit_dep import enforce_rate_limit
from app.core.rate_limiter_v2 import SlidingWindowRateLimiterV2, get_hourly_plan_limit


def _request(redis, path: str = "/api/v1/usage", method: str = "GET"):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(redis=redis)),
        method=method,
        url=SimpleNamespace(path=path),
    )


@pytest.mark.asyncio
async def test_plan_hourly_limits() -> None:
    assert get_hourly_plan_limit("free") == 100
    assert get_hourly_plan_limit("build") == 1000
    assert get_hourly_plan_limit("scale") == 10_000


@pytest.mark.asyncio
async def test_warning_header_at_eighty_percent() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user = AuthenticatedUser(id="u1", email="u@test.com", plan="free", is_test_key=False)
    request = _request(redis)

    for _ in range(79):
        await enforce_rate_limit(request, Response(), user)

    response = Response()
    await enforce_rate_limit(request, response, user)

    assert response.headers["X-RateLimit-Limit"] == "100"
    assert response.headers["X-RateLimit-Remaining"] == "20"
    assert "80%" in response.headers["X-RateLimit-Warning"]


@pytest.mark.asyncio
async def test_blocks_at_hundred_percent_with_retry_after() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user = AuthenticatedUser(id="u2", email="u@test.com", plan="free", is_test_key=False)
    request = _request(redis)

    for _ in range(100):
        await enforce_rate_limit(request, Response(), user)

    with pytest.raises(RateLimitError) as exc:
        await enforce_rate_limit(request, Response(), user)

    assert exc.value.headers is not None
    assert exc.value.headers["Retry-After"]


@pytest.mark.asyncio
async def test_endpoint_specific_limit_uses_heavy_bucket() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user = AuthenticatedUser(id="u3", email="u@test.com", plan="build", is_test_key=False)
    response = Response()

    await enforce_rate_limit(
        _request(redis, path="/api/v1/videos/generate", method="POST"),
        response,
        user,
    )

    assert response.headers["X-RateLimit-Limit"] == "10"


@pytest.mark.asyncio
async def test_time_window_resets_after_elapsed_time() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    current = {"value": 1000.0}
    limiter = SlidingWindowRateLimiterV2(redis, now_fn=lambda: current["value"])

    await limiter.check(identifier="u4", limit=1, window_seconds=3600)
    blocked = await limiter.check(identifier="u4", limit=1, window_seconds=3600)
    current["value"] += 3601
    allowed = await limiter.check(identifier="u4", limit=1, window_seconds=3600)

    assert blocked.allowed is False
    assert allowed.allowed is True


@pytest.mark.asyncio
async def test_users_are_isolated() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = SlidingWindowRateLimiterV2(redis)

    first = await limiter.check(identifier="user:a", limit=1, window_seconds=3600)
    second = await limiter.check(identifier="user:b", limit=1, window_seconds=3600)

    assert first.allowed is True
    assert second.allowed is True


@pytest.mark.asyncio
async def test_heavy_endpoint_has_separate_cap() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    user = AuthenticatedUser(id="u5", email="u@test.com", plan="scale", is_test_key=False)
    request = _request(redis, path="/api/v1/videos/generate", method="POST")

    for _ in range(10):
        await enforce_rate_limit(request, Response(), user)

    with pytest.raises(RateLimitError):
        await enforce_rate_limit(request, Response(), user)


@pytest.mark.asyncio
async def test_plan_upgrade_changes_limit_immediately() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    request = _request(redis)
    free_user = AuthenticatedUser(id="u6", email="u@test.com", plan="free", is_test_key=False)
    build_user = AuthenticatedUser(id="u6", email="u@test.com", plan="build", is_test_key=False)

    response = Response()
    await enforce_rate_limit(request, response, free_user)
    assert response.headers["X-RateLimit-Limit"] == "100"

    response = Response()
    await enforce_rate_limit(request, response, build_user)
    assert response.headers["X-RateLimit-Limit"] == "1000"
