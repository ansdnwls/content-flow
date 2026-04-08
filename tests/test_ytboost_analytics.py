"""Tests for YtBoost analytics dashboard API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from tests.fakes import FakeSupabase

USER_ID = str(uuid4())


def _make_user(fake: FakeSupabase) -> None:
    fake.insert_row("users", {"id": USER_ID, "email": "u@test.com", "plan": "creator"})


def _make_channel(
    fake: FakeSupabase,
    channel_id: str = "UC_chan1",
    name: str = "Chan 1",
    last_checked: str | None = None,
) -> str:
    row = fake.insert_row(
        "ytboost_subscriptions",
        {
            "user_id": USER_ID,
            "youtube_channel_id": channel_id,
            "channel_name": name,
            "auto_distribute": True,
            "target_platforms": ["tiktok", "instagram"],
            "auto_comment_mode": "auto",
            "subscribed_at": datetime.now(UTC).isoformat(),
            "last_checked_at": last_checked,
        },
    )
    return row["id"]


def _make_short(
    fake: FakeSupabase,
    channel_id: str = "UC_chan1",
    status: str = "pending",
    created_at: str | None = None,
) -> str:
    row = fake.insert_row(
        "ytboost_shorts",
        {
            "user_id": USER_ID,
            "source_video_id": f"vid_{uuid4().hex[:6]}",
            "source_channel_id": channel_id,
            "start_seconds": 10,
            "end_seconds": 70,
            "status": status,
            "created_at": created_at or datetime.now(UTC).isoformat(),
        },
    )
    return row["id"]


def _make_comment(
    fake: FakeSupabase,
    reply_status: str = "replied",
    created_at: str | None = None,
    updated_at: str | None = None,
) -> str:
    now = datetime.now(UTC).isoformat()
    row = fake.insert_row(
        "comments",
        {
            "user_id": USER_ID,
            "platform": "youtube",
            "platform_post_id": f"vid_{uuid4().hex[:6]}",
            "platform_comment_id": f"c_{uuid4().hex[:6]}",
            "author_id": "a1",
            "author_name": "Viewer",
            "text": "Great video!",
            "ai_reply": "Thanks!" if reply_status == "replied" else None,
            "reply_status": reply_status,
            "created_at": created_at or now,
            "updated_at": updated_at or now,
        },
    )
    return row["id"]


def _make_delivery(
    fake: FakeSupabase,
    platform: str = "tiktok",
    views: int = 0,
    likes: int = 0,
) -> None:
    fake.insert_row(
        "post_deliveries",
        {
            "owner_id": USER_ID,
            "post_id": str(uuid4()),
            "platform": platform,
            "platform_post_id": f"pp_{uuid4().hex[:6]}",
            "status": "published",
            "metadata": {"views": views, "likes": likes},
        },
    )


@pytest.fixture()
def setup(monkeypatch):
    from app.api.deps import AuthenticatedUser, get_current_user
    from app.main import app

    fake = FakeSupabase()
    _make_user(fake)

    test_user = AuthenticatedUser(
        id=USER_ID, email="u@test.com", plan="creator", is_test_key=True,
    )
    app.dependency_overrides[get_current_user] = lambda: test_user
    monkeypatch.setattr("app.api.v1.ytboost_analytics.get_supabase", lambda: fake)

    yield fake, app

    app.dependency_overrides.pop(get_current_user, None)


async def test_overview_empty(setup) -> None:
    """Overview returns zeros when no data exists."""
    _fake, app = setup

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/overview")

    assert resp.status_code == 200
    body = resp.json()
    assert body["this_month"]["shorts_extracted"] == 0
    assert body["this_month"]["shorts_published"] == 0
    assert body["this_month"]["comments_replied"] == 0
    assert body["channels"] == []


async def test_overview_with_data(setup) -> None:
    """Overview aggregates shorts and comments correctly per channel."""
    fake, app = setup

    _make_channel(fake, "UC_chan1", "Channel 1")
    _make_channel(fake, "UC_chan2", "Channel 2")
    _make_short(fake, "UC_chan1", "pending")
    _make_short(fake, "UC_chan1", "distributed")
    _make_short(fake, "UC_chan2", "approved")
    _make_comment(fake, "replied")
    _make_comment(fake, "replied")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/overview")

    assert resp.status_code == 200
    body = resp.json()
    assert body["this_month"]["shorts_extracted"] == 3
    assert body["this_month"]["shorts_published"] == 2
    assert body["this_month"]["comments_replied"] == 2
    assert len(body["channels"]) == 2

    chan1 = next(c for c in body["channels"] if c["youtube_channel_id"] == "UC_chan1")
    assert chan1["shorts_extracted"] == 2
    assert chan1["shorts_published"] == 1


async def test_shorts_performance_empty(setup) -> None:
    """Shorts performance returns empty when no shorts exist."""
    _fake, app = setup

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/shorts-performance")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_shorts"] == 0
    assert body["platforms"] == []


async def test_shorts_performance_with_deliveries(setup) -> None:
    """Shorts performance aggregates platform stats correctly."""
    fake, app = setup

    _make_short(fake, "UC_chan1", "distributed")
    _make_short(fake, "UC_chan1", "approved")
    _make_delivery(fake, "tiktok", views=1000, likes=50)
    _make_delivery(fake, "tiktok", views=2000, likes=100)
    _make_delivery(fake, "instagram", views=500, likes=30)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/shorts-performance")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_shorts"] == 2
    assert len(body["platforms"]) == 2

    tiktok = next(p for p in body["platforms"] if p["platform"] == "tiktok")
    assert tiktok["count"] == 2
    assert tiktok["avg_views"] == 1500
    assert tiktok["avg_likes"] == 75

    ig = next(p for p in body["platforms"] if p["platform"] == "instagram")
    assert ig["count"] == 1
    assert ig["avg_views"] == 500


async def test_comment_stats_empty(setup) -> None:
    """Comment stats returns zeros when no comments exist."""
    _fake, app = setup

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/comment-stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_comments"] == 0
    assert body["auto_ratio"] == 0.0
    assert body["avg_response_seconds"] is None


async def test_comment_stats_with_data(setup) -> None:
    """Comment stats calculates auto/manual ratio and avg response time."""
    fake, app = setup

    now = datetime.now(UTC)
    t1_created = (now - timedelta(hours=2)).isoformat()
    t1_updated = (now - timedelta(hours=1)).isoformat()

    _make_comment(fake, "replied", created_at=t1_created, updated_at=t1_updated)
    _make_comment(fake, "replied", created_at=t1_created, updated_at=t1_updated)
    _make_comment(fake, "review_pending")
    _make_comment(fake, "pending")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/comment-stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_comments"] == 4
    assert body["auto_replied"] == 2
    assert body["manual_replied"] == 1
    assert body["pending"] == 1
    assert body["auto_ratio"] == 0.5
    assert body["avg_response_seconds"] is not None
    assert body["avg_response_seconds"] > 0


async def test_channel_health_active(setup) -> None:
    """Channel health marks recently checked channels as active."""
    fake, app = setup

    recent = datetime.now(UTC).isoformat()
    _make_channel(fake, "UC_active", "Active Channel", last_checked=recent)
    _make_short(fake, "UC_active", "distributed")
    _make_short(fake, "UC_active", "pending")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/channel-health")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["channels"]) == 1
    ch = body["channels"][0]
    assert ch["status"] == "active"
    assert ch["shorts_count"] == 2
    assert ch["auto_distribute"] is True


async def test_channel_health_stale(setup) -> None:
    """Channel health marks old channels as stale."""
    fake, app = setup

    old = (datetime.now(UTC) - timedelta(days=14)).isoformat()
    _make_channel(fake, "UC_stale", "Stale Channel", last_checked=old)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ytboost/analytics/channel-health")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["channels"]) == 1
    assert body["channels"][0]["status"] == "stale"


async def test_analytics_auth_required() -> None:
    """All analytics endpoints require authentication."""
    from app.api.deps import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        endpoints = [
            "/api/v1/ytboost/analytics/overview",
            "/api/v1/ytboost/analytics/shorts-performance",
            "/api/v1/ytboost/analytics/comment-stats",
            "/api/v1/ytboost/analytics/channel-health",
        ]
        for url in endpoints:
            resp = await client.get(url)
            assert resp.status_code == 401, f"{url} should require auth"
