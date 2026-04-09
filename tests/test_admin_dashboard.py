from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient

from app.core.audit import reset_audit_writer
from app.core.auth import build_api_key_record
from tests.fakes import FakeSupabase


def _setup_admin(fake: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row(
        "users",
        {
            "id": user_id,
            "email": "admin@test.com",
            "full_name": "Admin",
            "plan": "enterprise",
            "is_active": True,
        },
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="admin", prefix="cf_admin")
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


def _setup_regular_user(
    fake: FakeSupabase,
    *,
    email: str,
    plan: str = "build",
    created_at: str | None = None,
) -> str:
    user_id = str(uuid4())
    fake.insert_row(
        "users",
        {
            "id": user_id,
            "email": email,
            "plan": plan,
            "is_active": True,
            "created_at": created_at or datetime.now(UTC).isoformat(),
        },
    )
    return user_id


def _patch_admin_stack(monkeypatch, fake: FakeSupabase) -> None:
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.audit.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)
    monkeypatch.setattr("app.services.admin_analytics.get_supabase", lambda: fake)


async def _client(app, admin_key: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    )


async def test_admin_dashboard_overview_ok(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    admin_id, admin_key = _setup_admin(fake)
    now = datetime.now(UTC)
    user_id = _setup_regular_user(fake, email="user@test.com", created_at=now.isoformat())

    fake.insert_row(
        "api_keys",
        {
            "user_id": user_id,
            "key_prefix": "cf_live",
            "hashed_key": "x",
            "key_preview": "x",
            "last_used_at": now.isoformat(),
            "is_active": True,
        },
    )
    fake.insert_row(
        "api_keys",
        {
            "user_id": admin_id,
            "key_prefix": "cf_live",
            "hashed_key": "x",
            "key_preview": "x",
            "last_used_at": now.isoformat(),
            "is_active": True,
        },
    )
    fake.insert_row(
        "payments",
        {
            "user_id": user_id,
            "amount": 120.5,
            "status": "succeeded",
            "created_at": now.isoformat(),
        },
    )
    fake.insert_row(
        "posts",
        {"owner_id": user_id, "status": "published", "created_at": now.isoformat()},
    )
    fake.insert_row(
        "video_jobs",
        {
            "owner_id": user_id,
            "topic": "t",
            "mode": "general",
            "status": "completed",
            "created_at": now.isoformat(),
        },
    )
    fake.insert_row(
        "audit_logs",
        {
            "user_id": user_id,
            "action": "api.posts.list",
            "resource": "posts",
            "created_at": now.isoformat(),
            "metadata": {"status_code": 200, "duration_ms": 120.0},
        },
    )
    fake.insert_row(
        "audit_logs",
        {
            "user_id": user_id,
            "action": "api.posts.create",
            "resource": "posts",
            "created_at": now.isoformat(),
            "metadata": {"status_code": 500, "duration_ms": 240.0},
        },
    )

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr("app.services.admin_analytics.get_redis", lambda: redis)
    app.state.redis = redis

    try:
        async with await _client(app, admin_key) as client:
            response = await client.get("/api/v1/admin/dashboard/overview")
    finally:
        await reset_audit_writer()

    assert response.status_code == 200
    body = response.json()
    assert body["total_users"] == 2
    assert body["active_users_dau"] == 2
    assert body["new_signups"] >= 1
    assert body["revenue_this_month"] == 120.5
    assert body["total_posts"] == 1
    assert body["total_videos"] == 1
    assert body["error_rate"] == 50.0
    assert body["average_response_time_ms"] == 180.0


async def test_admin_dashboard_non_admin_blocked(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    user_id = _setup_regular_user(fake, email="build@test.com", plan="build")
    issued, record = build_api_key_record(user_id=uuid4(), name="admin", prefix="cf_admin")
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)

    _patch_admin_stack(monkeypatch, fake)

    async with await _client(app, issued.raw_key) as client:
        response = await client.get("/api/v1/admin/dashboard/overview")

    assert response.status_code == 403


async def test_admin_dashboard_growth_timeseries(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    base = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
    user_id = _setup_regular_user(fake, email="g1@test.com", created_at=base.isoformat())
    _setup_regular_user(
        fake,
        email="g2@test.com",
        created_at=(base + timedelta(days=1)).isoformat(),
    )
    fake.insert_row(
        "payments",
        {
            "user_id": user_id,
            "amount": 99.0,
            "status": "succeeded",
            "created_at": base.isoformat(),
        },
    )
    fake.insert_row(
        "posts",
        {"owner_id": user_id, "status": "published", "created_at": base.isoformat()},
    )
    fake.insert_row(
        "video_jobs",
        {
            "owner_id": user_id,
            "topic": "t",
            "mode": "general",
            "status": "completed",
            "created_at": (base + timedelta(days=1)).isoformat(),
        },
    )
    fake.insert_row(
        "audit_logs",
        {
            "user_id": user_id,
            "action": "api.usage.summary",
            "resource": "usage",
            "created_at": base.isoformat(),
        },
    )

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr(
        "app.services.admin_analytics.get_redis",
        lambda: fakeredis.aioredis.FakeRedis(decode_responses=True),
    )

    async with await _client(app, admin_key) as client:
        response = await client.get(
            "/api/v1/admin/dashboard/growth",
            params={
                "granularity": "day",
                "start_date": "2026-04-01",
                "end_date": "2026-04-02",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["granularity"] == "day"
    assert [point["bucket"] for point in body["points"]] == ["2026-04-01", "2026-04-02"]
    assert body["points"][0]["signups"] == 1
    assert body["points"][0]["revenue"] == 99.0


async def test_admin_dashboard_top_users_sorted(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    now = datetime.now(UTC).isoformat()
    user_a = _setup_regular_user(fake, email="a@test.com")
    user_b = _setup_regular_user(fake, email="b@test.com")

    for _ in range(3):
        fake.insert_row(
            "audit_logs",
            {
                "user_id": user_b,
                "action": "api.call",
                "resource": "api",
                "created_at": now,
            },
        )
    fake.insert_row("posts", {"owner_id": user_b, "status": "published", "created_at": now})
    fake.insert_row(
        "video_jobs",
        {
            "owner_id": user_a,
            "topic": "t",
            "mode": "general",
            "status": "completed",
            "created_at": now,
        },
    )

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr(
        "app.services.admin_analytics.get_redis",
        lambda: fakeredis.aioredis.FakeRedis(decode_responses=True),
    )

    async with await _client(app, admin_key) as client:
        response = await client.get("/api/v1/admin/dashboard/top-users")

    assert response.status_code == 200
    users = response.json()["users"]
    assert users[0]["user_id"] == user_b
    assert users[0]["total_usage"] == 4


async def test_admin_dashboard_churn_logic(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    end = datetime(2026, 4, 9, 12, 0, tzinfo=UTC)
    risky = _setup_regular_user(fake, email="risk@test.com")
    stable = _setup_regular_user(fake, email="stable@test.com")

    fake.insert_row(
        "api_keys",
        {
            "user_id": risky,
            "key_prefix": "cf_live",
            "hashed_key": "x",
            "key_preview": "x",
            "last_used_at": (end - timedelta(days=10)).isoformat(),
            "is_active": True,
        },
    )
    fake.insert_row(
        "api_keys",
        {
            "user_id": stable,
            "key_prefix": "cf_live",
            "hashed_key": "x",
            "key_preview": "x",
            "last_used_at": (end - timedelta(days=1)).isoformat(),
            "is_active": True,
        },
    )
    for delta in (10, 11, 12):
        fake.insert_row(
            "audit_logs",
            {
                "user_id": risky,
                "action": "api.call",
                "resource": "api",
                "created_at": (end - timedelta(days=delta)).isoformat(),
            },
        )
    fake.insert_row(
        "audit_logs",
        {
            "user_id": stable,
            "action": "api.call",
            "resource": "api",
            "created_at": (end - timedelta(days=1)).isoformat(),
        },
    )

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr(
        "app.services.admin_analytics.get_redis",
        lambda: fakeredis.aioredis.FakeRedis(decode_responses=True),
    )

    async with await _client(app, admin_key) as client:
        response = await client.get(
            "/api/v1/admin/dashboard/churn",
            params={"end_date": "2026-04-09"},
        )

    assert response.status_code == 200
    users = response.json()["users"]
    assert users[0]["user_id"] == risky
    assert "inactive" in users[0]["reasons"]


async def test_admin_dashboard_caching(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    _setup_regular_user(fake, email="cache@test.com")
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr("app.services.admin_analytics.get_redis", lambda: redis)
    app.state.redis = redis

    async with await _client(app, admin_key) as client:
        first = await client.get("/api/v1/admin/dashboard/overview")
        users_after_first = fake.query_counts.get("users", 0)
        second = await client.get("/api/v1/admin/dashboard/overview")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert fake.query_counts.get("users", 0) == users_after_first + 1


async def test_admin_dashboard_creates_audit_log(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    admin_id, admin_key = _setup_admin(fake)
    _setup_regular_user(fake, email="audit@test.com")

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr(
        "app.services.admin_analytics.get_redis",
        lambda: fakeredis.aioredis.FakeRedis(decode_responses=True),
    )

    try:
        async with await _client(app, admin_key) as client:
            response = await client.get("/api/v1/admin/dashboard/overview")
    finally:
        await reset_audit_writer()

    assert response.status_code == 200
    audit = fake.tables["audit_logs"][-1]
    assert audit["user_id"] == admin_id
    assert audit["action"] == "admin.dashboard.overview.view"


async def test_admin_dashboard_date_range_filter(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    _setup_regular_user(fake, email="old@test.com", created_at="2026-03-01T00:00:00+00:00")
    _setup_regular_user(fake, email="new@test.com", created_at="2026-04-03T00:00:00+00:00")

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr(
        "app.services.admin_analytics.get_redis",
        lambda: fakeredis.aioredis.FakeRedis(decode_responses=True),
    )

    async with await _client(app, admin_key) as client:
        response = await client.get(
            "/api/v1/admin/dashboard/overview",
            params={"start_date": "2026-04-01", "end_date": "2026-04-09"},
        )

    assert response.status_code == 200
    assert response.json()["new_signups"] == 1


async def test_admin_dashboard_empty_data(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr(
        "app.services.admin_analytics.get_redis",
        lambda: fakeredis.aioredis.FakeRedis(decode_responses=True),
    )

    async with await _client(app, admin_key) as client:
        response = await client.get("/api/v1/admin/dashboard/top-users")

    assert response.status_code == 200
    assert response.json()["users"] == []


async def test_admin_dashboard_rate_limit_applies(monkeypatch) -> None:
    from app.core.rate_limiter_v2 import RateLimitPolicy
    from app.main import app

    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    _patch_admin_stack(monkeypatch, fake)
    monkeypatch.setattr("app.services.admin_analytics.get_redis", lambda: redis)
    app.state.redis = redis
    monkeypatch.setattr(
        "app.core.rate_limit_dep.get_rate_limit_policies",
        lambda user, method, path: [
            RateLimitPolicy(
                name="global",
                limit=1,
                window_seconds=3600,
                scope="global",
            )
        ],
    )

    async with await _client(app, admin_key) as client:
        first = await client.get("/api/v1/admin/dashboard/overview")
        second = await client.get("/api/v1/admin/dashboard/overview")

    assert first.status_code == 200
    assert second.status_code == 429
