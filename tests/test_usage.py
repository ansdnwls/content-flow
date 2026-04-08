"""Tests for Usage Dashboard API, billing, and rate limit dependency."""

from __future__ import annotations

from uuid import uuid4

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from tests.fakes import FakeSupabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_user_and_key(fake_supabase: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users", {"id": user_id, "email": "usage@example.com", "plan": "build"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)
    return user_id, issued.raw_key


# ---------------------------------------------------------------------------
# Billing / Usage functions
# ---------------------------------------------------------------------------

async def test_get_usage_summary(monkeypatch) -> None:
    from app.core.billing import get_usage_summary

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())

    fake_supabase.insert_row("posts", {
        "owner_id": user_id, "status": "published",
    })
    fake_supabase.insert_row("posts", {
        "owner_id": user_id, "status": "pending",
    })
    fake_supabase.insert_row("video_jobs", {
        "owner_id": user_id, "status": "completed",
    })
    fake_supabase.insert_row("social_accounts", {
        "owner_id": user_id, "platform": "youtube", "handle": "@test",
    })

    monkeypatch.setattr("app.core.billing.get_supabase", lambda: fake_supabase)

    summary = await get_usage_summary(user_id, "build")
    assert summary["plan"] == "build"
    assert summary["posts_used"] == 2
    assert summary["posts_limit"] == 200
    assert summary["videos_used"] == 1
    assert summary["videos_limit"] == 20
    assert summary["accounts_used"] == 1
    assert summary["accounts_limit"] == 5
    assert summary["rate_limit_per_minute"] == 60


async def test_get_usage_history(monkeypatch) -> None:
    from app.core.billing import get_usage_history

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())

    monkeypatch.setattr("app.core.billing.get_supabase", lambda: fake_supabase)

    history = await get_usage_history(user_id, days=7)
    assert len(history) <= 7
    assert len(history) >= 6  # timezone boundary tolerance
    assert all("date" in entry and "posts" in entry and "videos" in entry for entry in history)


async def test_check_post_limit_under_limit(monkeypatch) -> None:
    from app.core.billing import check_post_limit

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())

    monkeypatch.setattr("app.core.billing.get_supabase", lambda: fake_supabase)

    # Should not raise — 0 posts used, limit is 20
    await check_post_limit(user_id, "free")


async def test_check_post_limit_over_limit(monkeypatch) -> None:
    import pytest

    from app.core.billing import check_post_limit
    from app.core.errors import BillingLimitError

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())

    for _ in range(20):
        fake_supabase.insert_row("posts", {"owner_id": user_id, "status": "published"})

    monkeypatch.setattr("app.core.billing.get_supabase", lambda: fake_supabase)

    with pytest.raises(BillingLimitError):
        await check_post_limit(user_id, "free")


async def test_check_video_limit_over_limit(monkeypatch) -> None:
    import pytest

    from app.core.billing import check_video_limit
    from app.core.errors import BillingLimitError

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())

    for _ in range(3):
        fake_supabase.insert_row("video_jobs", {"owner_id": user_id, "status": "completed"})

    monkeypatch.setattr("app.core.billing.get_supabase", lambda: fake_supabase)

    with pytest.raises(BillingLimitError):
        await check_video_limit(user_id, "free")


# ---------------------------------------------------------------------------
# Rate limit dependency
# ---------------------------------------------------------------------------

async def test_rate_limit_headers(monkeypatch) -> None:
    from types import SimpleNamespace

    from fastapi import Response

    from app.api.deps import AuthenticatedUser
    from app.core.rate_limit_dep import enforce_rate_limit

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    user = AuthenticatedUser(id="u1", email="t@t.com", plan="free", is_test_key=False)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=redis)))
    response = Response()

    await enforce_rate_limit(request, response, user)

    assert response.headers.get("X-RateLimit-Limit") == "10"
    assert response.headers.get("X-RateLimit-Remaining") == "9"
    assert response.headers.get("X-RateLimit-Reset") is not None


async def test_rate_limit_blocks_over_limit(monkeypatch) -> None:
    from types import SimpleNamespace

    import pytest
    from fastapi import Response

    from app.api.deps import AuthenticatedUser
    from app.core.errors import RateLimitError
    from app.core.rate_limit_dep import enforce_rate_limit

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    user = AuthenticatedUser(id="u2", email="t@t.com", plan="free", is_test_key=False)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=redis)))

    # Exhaust the limit (10 requests for free plan)
    for _ in range(10):
        response = Response()
        await enforce_rate_limit(request, response, user)

    # 11th request should raise
    response = Response()
    with pytest.raises(RateLimitError):
        await enforce_rate_limit(request, response, user)


async def test_rate_limit_no_redis_passes(monkeypatch) -> None:
    from types import SimpleNamespace

    from fastapi import Response

    from app.api.deps import AuthenticatedUser
    from app.core.rate_limit_dep import enforce_rate_limit

    user = AuthenticatedUser(id="u3", email="t@t.com", plan="free", is_test_key=False)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = Response()

    # Should not raise — fail-open when no Redis
    await enforce_rate_limit(request, response, user)


async def test_rate_limit_plan_scaling() -> None:
    from app.core.billing import get_rate_limit

    assert get_rate_limit("free") == 10
    assert get_rate_limit("build") == 60
    assert get_rate_limit("scale") == 300
    assert get_rate_limit("enterprise") == 1000
    assert get_rate_limit("unknown") == 10  # falls back to free


# ---------------------------------------------------------------------------
# Usage API endpoints
# ---------------------------------------------------------------------------

async def test_usage_api_summary(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)

    fake_supabase.insert_row("posts", {"owner_id": user_id, "status": "published"})
    fake_supabase.insert_row("video_jobs", {"owner_id": user_id, "status": "completed"})

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr("app.core.billing.get_supabase", lambda: fake_supabase)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] == "build"
        assert body["posts_used"] == 1
        assert body["posts_limit"] == 200
        assert body["videos_used"] == 1
        assert body["rate_limit_per_minute"] == 60


async def test_usage_api_history(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr("app.core.billing.get_supabase", lambda: fake_supabase)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/usage/history?days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["days"] == 7
        assert len(body["data"]) <= 7
        assert len(body["data"]) >= 6  # timezone boundary tolerance


async def test_usage_summary_endpoint_is_cached(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    _, raw_key = _setup_user_and_key(fake_supabase)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    calls = {"count": 0}

    async def fake_usage_summary(owner_id: str, plan: str, workspace_id=None) -> dict:
        calls["count"] += 1
        return {
            "plan": plan,
            "posts_used": 3,
            "posts_limit": 200,
            "videos_used": 1,
            "videos_limit": 20,
            "accounts_used": 2,
            "accounts_limit": 5,
            "rate_limit_per_minute": 60,
        }

    async def fake_cache_redis():
        return redis

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr("app.api.v1.usage.get_usage_summary", fake_usage_summary)
    monkeypatch.setattr("app.core.cache.get_redis", fake_cache_redis)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        first = await client.get("/api/v1/usage")
        second = await client.get("/api/v1/usage")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["posts_used"] == 3
    assert second.json()["posts_used"] == 3
    assert calls["count"] == 1
