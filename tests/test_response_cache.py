"""Tests for Redis-backed HTTP response caching."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import fakeredis.aioredis
from fastapi import Depends, FastAPI, Header, Request, Response
from httpx import ASGITransport, AsyncClient

from app.api.deps import AuthenticatedUser, get_current_user
from app.core.response_cache import (
    ResponseCacheInvalidationMiddleware,
    build_cache_hash,
    cached_response,
    invalidate_path,
    invalidate_user_cache,
)
from app.main import app
from tests.fakes import FakeSupabase


def _build_test_app(*, ttl: int = 300) -> tuple[FastAPI, dict[str, int]]:
    test_app = FastAPI()
    test_app.add_middleware(ResponseCacheInvalidationMiddleware)
    calls = {"cached": 0, "errors": 0, "posts": 0}

    async def get_user(
        request: Request,
        x_user_id: str = Header(default="user-1", alias="X-User-Id"),
    ) -> SimpleNamespace:
        request.state.user_id = x_user_id
        return SimpleNamespace(id=x_user_id)

    current_user = Depends(get_user)

    @test_app.get("/cached")
    @cached_response(ttl=ttl, key_prefix="test-cached")
    async def get_cached(
        request: Request,
        response: Response,
        user: SimpleNamespace = current_user,
        q: str = "default",
    ) -> dict[str, str | int]:
        calls["cached"] += 1
        return {
            "count": calls["cached"],
            "user_id": user.id,
            "query": q,
            "language": request.headers.get("accept-language", ""),
        }

    @test_app.get("/error")
    @cached_response(ttl=ttl, key_prefix="test-error")
    async def get_error(
        response: Response,
        user: SimpleNamespace = current_user,
    ) -> dict[str, int]:
        calls["errors"] += 1
        response.status_code = 500
        return {"count": calls["errors"]}

    @test_app.post("/cached")
    @cached_response(ttl=ttl, key_prefix="test-post")
    async def create_cached(
        user: SimpleNamespace = current_user,
    ) -> dict[str, int | str]:
        calls["posts"] += 1
        return {"count": calls["posts"], "user": user.id}

    @test_app.post("/mutate")
    async def mutate(user: SimpleNamespace = current_user) -> dict[str, str]:
        return {"status": f"updated:{user.id}"}

    return test_app, calls


def _make_client(test_app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver")


async def test_response_cache_hit_and_miss_headers(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        first = await client.get("/cached")
        second = await client.get("/cached")

    assert first.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert first.json()["count"] == 1
    assert second.json()["count"] == 1
    assert calls["cached"] == 1


async def test_response_cache_ttl_expiration(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app(ttl=1)

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        first = await client.get("/cached")
        await asyncio.sleep(1.1)
        second = await client.get("/cached")

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    assert second.json()["count"] == 2
    assert calls["cached"] == 2


async def test_response_cache_isolated_by_user(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        first_user = await client.get("/cached", headers={"X-User-Id": "user-1"})
        second_user = await client.get("/cached", headers={"X-User-Id": "user-2"})
        first_user_again = await client.get("/cached", headers={"X-User-Id": "user-1"})

    assert first_user.headers["X-Cache"] == "MISS"
    assert second_user.headers["X-Cache"] == "MISS"
    assert first_user_again.headers["X-Cache"] == "HIT"
    assert calls["cached"] == 2


async def test_response_cache_isolated_by_language(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        korean = await client.get("/cached", headers={"Accept-Language": "ko"})
        english = await client.get("/cached", headers={"Accept-Language": "en"})
        korean_again = await client.get("/cached", headers={"Accept-Language": "ko"})

    assert korean.headers["X-Cache"] == "MISS"
    assert english.headers["X-Cache"] == "MISS"
    assert korean_again.headers["X-Cache"] == "HIT"
    assert calls["cached"] == 2


async def test_invalidate_user_cache_clears_only_target_user(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        await client.get("/cached", headers={"X-User-Id": "user-1"})
        await client.get("/cached", headers={"X-User-Id": "user-2"})
        deleted = await invalidate_user_cache("user-1")
        first_user = await client.get("/cached", headers={"X-User-Id": "user-1"})
        second_user = await client.get("/cached", headers={"X-User-Id": "user-2"})

    assert deleted == 1
    assert first_user.headers["X-Cache"] == "MISS"
    assert second_user.headers["X-Cache"] == "HIT"
    assert calls["cached"] == 3


async def test_invalidate_path_clears_matching_entries(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        await client.get("/cached?q=one")
        await client.get("/cached?q=two")
        deleted = await invalidate_path("/cached")
        after = await client.get("/cached?q=one")

    assert deleted == 2
    assert after.headers["X-Cache"] == "MISS"
    assert calls["cached"] == 3


async def test_successful_write_automatically_invalidates_user_cache(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    fake_sb = FakeSupabase()
    test_user = AuthenticatedUser(
        id="user-123",
        email="owner@example.com",
        plan="pro",
        is_test_key=False,
    )
    fake_sb.insert_row(
        "users",
        {
            "id": test_user.id,
            "email": test_user.email,
            "full_name": "Before",
            "plan": test_user.plan,
            "language": "ko",
            "timezone": "Asia/Seoul",
        },
    )

    async def fake_get_redis():
        return redis

    async def override_current_user(request: Request) -> AuthenticatedUser:
        request.state.user_id = test_user.id
        return test_user

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)
    monkeypatch.setattr("app.api.v1.users.get_supabase", lambda: fake_sb)
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            first = await client.get("/api/v1/users/me")
            second = await client.get("/api/v1/users/me")
            patch_resp = await client.patch(
                "/api/v1/users/me",
                json={"full_name": "After"},
            )
            after_patch = await client.get("/api/v1/users/me")
    finally:
        app.dependency_overrides.clear()

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert patch_resp.status_code == 200
    assert after_patch.headers["X-Cache"] == "MISS"
    assert after_patch.json()["full_name"] == "After"


async def test_cache_passes_through_when_redis_unavailable(monkeypatch) -> None:
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        first = await client.get("/cached")
        second = await client.get("/cached")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "MISS"
    assert calls["cached"] == 2


async def test_error_responses_are_not_cached(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        first = await client.get("/error")
        second = await client.get("/error")

    assert first.status_code == 500
    assert second.status_code == 500
    assert calls["errors"] == 2


async def test_post_requests_are_not_cached(monkeypatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    test_app, calls = _build_test_app()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.core.response_cache.get_redis", fake_get_redis)

    async with _make_client(test_app) as client:
        first = await client.post("/cached")
        second = await client.post("/cached")

    assert first.status_code == 200
    assert second.status_code == 200
    assert "X-Cache" not in first.headers
    assert "X-Cache" not in second.headers
    assert calls["posts"] == 2


def test_cache_hash_avoids_key_collisions() -> None:
    first = build_cache_hash(
        method="GET",
        path="/api/v1/example",
        query_items=[("ab", "c")],
        user_id="user-1",
        accept_language="ko",
    )
    second = build_cache_hash(
        method="GET",
        path="/api/v1/example",
        query_items=[("a", "bc")],
        user_id="user-1",
        accept_language="ko",
    )

    assert first != second
