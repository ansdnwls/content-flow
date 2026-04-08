"""Tests for Analytics Engine: adapters, service, API, and worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import fakeredis.aioredis
import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.adapters.base import AnalyticsData
from app.core.auth import build_api_key_record
from tests.fakes import FakeSupabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_user_and_key(
    fake_supabase: FakeSupabase,
    plan: str = "build",
) -> tuple[str, str]:
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users",
        {"id": user_id, "email": "analytics@example.com", "plan": plan},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)
    return user_id, issued.raw_key


def _insert_snapshot(
    fake_supabase: FakeSupabase,
    owner_id: str,
    *,
    platform: str = "youtube",
    platform_post_id: str | None = None,
    snapshot_date: str | None = None,
    views: int = 100,
    likes: int = 10,
    comments: int = 5,
    shares: int = 2,
    followers: int = 0,
    impressions: int = 0,
    reach: int = 0,
    engagement_rate: float = 0.0,
) -> dict:
    row = {
        "owner_id": owner_id,
        "platform": platform,
        "platform_post_id": platform_post_id,
        "snapshot_date": snapshot_date
        or datetime.now(UTC).strftime("%Y-%m-%d"),
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "followers": followers,
        "impressions": impressions,
        "reach": reach,
        "engagement_rate": engagement_rate,
    }
    return fake_supabase.insert_row("analytics_snapshots", row)


# ---------------------------------------------------------------------------
# Adapter get_analytics tests
# ---------------------------------------------------------------------------


@respx.mock
async def test_youtube_get_analytics_post() -> None:
    from app.adapters.youtube import YouTubeAdapter

    respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "vid1",
                        "statistics": {
                            "viewCount": "1000",
                            "likeCount": "50",
                            "commentCount": "10",
                        },
                    }
                ]
            },
        ),
    )

    adapter = YouTubeAdapter()
    results = await adapter.get_analytics(
        "vid1", {"access_token": "test"},
    )
    assert len(results) == 1
    assert results[0].views == 1000
    assert results[0].likes == 50
    assert results[0].comments == 10
    assert results[0].platform == "youtube"


@respx.mock
async def test_youtube_get_analytics_channel() -> None:
    from app.adapters.youtube import YouTubeAdapter

    respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "statistics": {
                            "viewCount": "50000",
                            "subscriberCount": "1200",
                        }
                    }
                ]
            },
        ),
    )

    adapter = YouTubeAdapter()
    results = await adapter.get_analytics(
        None, {"access_token": "test"},
    )
    assert len(results) == 1
    assert results[0].followers == 1200
    assert results[0].views == 50000


@respx.mock
async def test_tiktok_get_analytics_post() -> None:
    from app.adapters.tiktok import TikTokAdapter

    respx.post(
        "https://open.tiktokapis.com/v2/video/query/"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "videos": [
                        {
                            "id": "tt1",
                            "view_count": 5000,
                            "like_count": 200,
                            "comment_count": 30,
                            "share_count": 15,
                        }
                    ]
                }
            },
        ),
    )

    adapter = TikTokAdapter()
    results = await adapter.get_analytics(
        "tt1", {"access_token": "test"},
    )
    assert len(results) == 1
    assert results[0].views == 5000
    assert results[0].shares == 15
    assert results[0].platform == "tiktok"


@respx.mock
async def test_tiktok_get_analytics_account() -> None:
    from app.adapters.tiktok import TikTokAdapter

    respx.get(
        "https://open.tiktokapis.com/v2/user/info/"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "user": {
                        "follower_count": 8000,
                        "likes_count": 120000,
                    }
                }
            },
        ),
    )

    adapter = TikTokAdapter()
    results = await adapter.get_analytics(
        None, {"access_token": "test"},
    )
    assert len(results) == 1
    assert results[0].followers == 8000
    assert results[0].likes == 120000


@respx.mock
async def test_instagram_get_analytics_post() -> None:
    from app.adapters.instagram import InstagramAdapter

    respx.get(
        "https://graph.facebook.com/v21.0/post1/insights"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "impressions", "values": [{"value": 3000}]},
                    {"name": "reach", "values": [{"value": 2500}]},
                    {"name": "likes", "values": [{"value": 150}]},
                    {"name": "comments", "values": [{"value": 20}]},
                    {"name": "shares", "values": [{"value": 8}]},
                ]
            },
        ),
    )

    adapter = InstagramAdapter()
    results = await adapter.get_analytics(
        "post1",
        {"access_token": "test", "ig_user_id": "ig1"},
    )
    assert len(results) == 1
    assert results[0].impressions == 3000
    assert results[0].reach == 2500
    assert results[0].platform == "instagram"


@respx.mock
async def test_instagram_get_analytics_account() -> None:
    from app.adapters.instagram import InstagramAdapter

    respx.get(
        "https://graph.facebook.com/v21.0/ig1"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"followers_count": 5000, "media_count": 120},
        ),
    )

    adapter = InstagramAdapter()
    results = await adapter.get_analytics(
        None,
        {"access_token": "test", "ig_user_id": "ig1"},
    )
    assert len(results) == 1
    assert results[0].followers == 5000


@respx.mock
async def test_x_twitter_get_analytics_post() -> None:
    from app.adapters.x_twitter import XTwitterAdapter

    respx.get("https://api.x.com/2/tweets/tweet1").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "id": "tweet1",
                    "public_metrics": {
                        "impression_count": 8000,
                        "like_count": 400,
                        "reply_count": 30,
                        "retweet_count": 20,
                        "quote_count": 10,
                    },
                }
            },
        ),
    )

    adapter = XTwitterAdapter()
    results = await adapter.get_analytics("tweet1", {"access_token": "test"})
    assert len(results) == 1
    assert results[0].views == 8000
    assert results[0].shares == 30
    assert results[0].platform == "x_twitter"


@respx.mock
async def test_x_twitter_get_analytics_account() -> None:
    from app.adapters.x_twitter import XTwitterAdapter

    respx.get("https://api.x.com/2/users/me").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"public_metrics": {"followers_count": 3200}}},
        ),
    )

    adapter = XTwitterAdapter()
    results = await adapter.get_analytics(None, {"access_token": "test"})
    assert len(results) == 1
    assert results[0].followers == 3200


@respx.mock
async def test_linkedin_get_analytics_post() -> None:
    from app.adapters.linkedin import LinkedInAdapter

    respx.get("https://api.linkedin.com/rest/socialActions/urn:li:share:1").mock(
        return_value=httpx.Response(
            200,
            json={
                "likesSummary": {"totalLikes": 50},
                "commentsSummary": {"totalFirstLevelComments": 7},
                "sharesSummary": {"count": 4},
                "impressionSummary": {"count": 1500},
            },
        ),
    )

    adapter = LinkedInAdapter()
    results = await adapter.get_analytics(
        "urn:li:share:1",
        {"access_token": "test", "author_urn": "urn:li:person:me"},
    )
    assert len(results) == 1
    assert results[0].views == 1500
    assert results[0].likes == 50
    assert results[0].platform == "linkedin"


@respx.mock
async def test_linkedin_get_analytics_account() -> None:
    from app.adapters.linkedin import LinkedInAdapter

    respx.get("https://api.linkedin.com/v2/networkSizes/urn:li:person:me").mock(
        return_value=httpx.Response(200, json={"firstDegreeSize": 1200}),
    )

    adapter = LinkedInAdapter()
    results = await adapter.get_analytics(
        None,
        {"access_token": "test", "author_urn": "urn:li:person:me"},
    )
    assert len(results) == 1
    assert results[0].followers == 1200


@respx.mock
async def test_facebook_get_analytics_post() -> None:
    from app.adapters.facebook import FacebookAdapter

    respx.get("https://graph.facebook.com/v19.0/post1/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "post_impressions", "values": [{"value": 5000}]},
                    {"name": "post_impressions_unique", "values": [{"value": 4200}]},
                    {"name": "post_reactions_like_total", "values": [{"value": 180}]},
                    {"name": "post_comments", "values": [{"value": 25}]},
                    {"name": "post_shares", "values": [{"value": 12}]},
                ]
            },
        ),
    )

    adapter = FacebookAdapter()
    results = await adapter.get_analytics(
        "post1",
        {"page_access_token": "test", "page_id": "page_1"},
    )
    assert len(results) == 1
    assert results[0].impressions == 5000
    assert results[0].reach == 4200
    assert results[0].platform == "facebook"


@respx.mock
async def test_facebook_get_analytics_account() -> None:
    from app.adapters.facebook import FacebookAdapter

    respx.get("https://graph.facebook.com/v19.0/page_1").mock(
        return_value=httpx.Response(200, json={"followers_count": 9100}),
    )

    adapter = FacebookAdapter()
    results = await adapter.get_analytics(
        None,
        {"page_access_token": "test", "page_id": "page_1"},
    )
    assert len(results) == 1
    assert results[0].followers == 9100


@respx.mock
async def test_threads_get_analytics_post() -> None:
    from app.adapters.threads import ThreadsAdapter

    respx.get("https://graph.threads.net/v1.0/thread1/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "views", "values": [{"value": 7000}]},
                    {"name": "likes", "values": [{"value": 300}]},
                    {"name": "replies", "values": [{"value": 45}]},
                    {"name": "reposts", "values": [{"value": 15}]},
                    {"name": "quotes", "values": [{"value": 5}]},
                ]
            },
        ),
    )

    adapter = ThreadsAdapter()
    results = await adapter.get_analytics(
        "thread1",
        {"access_token": "test", "threads_user_id": "user_1"},
    )
    assert len(results) == 1
    assert results[0].views == 7000
    assert results[0].shares == 20
    assert results[0].platform == "threads"


@respx.mock
async def test_threads_get_analytics_account() -> None:
    from app.adapters.threads import ThreadsAdapter

    respx.get("https://graph.threads.net/v1.0/me").mock(
        return_value=httpx.Response(200, json={"followers_count": 6400}),
    )

    adapter = ThreadsAdapter()
    results = await adapter.get_analytics(
        None,
        {"access_token": "test", "threads_user_id": "user_1"},
    )
    assert len(results) == 1
    assert results[0].followers == 6400


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


async def test_collect_snapshot(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())

    async def mock_get_analytics(self, post_id, creds):
        return [
            AnalyticsData(
                platform="youtube",
                platform_post_id="vid1",
                views=500,
                likes=25,
            )
        ]

    from app.adapters.youtube import YouTubeAdapter

    monkeypatch.setattr(YouTubeAdapter, "get_analytics", mock_get_analytics)
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    result = await service.collect_snapshot(
        user_id, "youtube", {"access_token": "test"}, "vid1",
    )
    assert len(result) == 1
    assert result[0]["views"] == 500
    assert len(fake_supabase.tables["analytics_snapshots"]) == 1


@pytest.mark.parametrize(
    ("platform", "module_name", "class_name", "credentials"),
    [
        ("x_twitter", "x_twitter", "XTwitterAdapter", {"access_token": "test"}),
        (
            "linkedin",
            "linkedin",
            "LinkedInAdapter",
            {"access_token": "test", "author_urn": "urn:li:person:me"},
        ),
        (
            "facebook",
            "facebook",
            "FacebookAdapter",
            {"page_access_token": "test", "page_id": "page_1"},
        ),
        (
            "threads",
            "threads",
            "ThreadsAdapter",
            {"access_token": "test", "threads_user_id": "user_1"},
        ),
    ],
)
async def test_collect_snapshot_expanded_platforms(
    monkeypatch,
    platform: str,
    module_name: str,
    class_name: str,
    credentials: dict[str, str],
) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    monkeypatch.setattr("app.services.analytics_service.get_supabase", lambda: fake_supabase)

    module = __import__(f"app.adapters.{module_name}", fromlist=[class_name])
    adapter_cls = getattr(module, class_name)

    async def fake_get_analytics(self, post_id, creds):
        return [
            AnalyticsData(
                platform=platform,
                platform_post_id="post_1",
                views=250,
                likes=25,
                comments=5,
                shares=2,
            )
        ]

    monkeypatch.setattr(adapter_cls, "get_analytics", fake_get_analytics)

    service = AnalyticsService()
    result = await service.collect_snapshot(
        "u1",
        platform,
        credentials,
        "post_1",
    )
    assert len(result) == 1
    assert result[0]["platform"] == platform


async def test_get_dashboard(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", views=1000, likes=50, comments=10,
        shares=5, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="tiktok", views=2000, likes=100, comments=20,
        shares=15, snapshot_date=today,
    )

    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    dashboard = await service.get_dashboard(user_id, "30d")
    assert dashboard["total_views"] == 3000
    assert dashboard["total_likes"] == 150
    assert dashboard["total_comments"] == 30
    assert dashboard["total_shares"] == 20
    assert dashboard["period"] == "30d"
    assert dashboard["snapshot_count"] == 2


async def test_get_dashboard_period_filter(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    old_date = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id, views=1000, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id, views=500, snapshot_date=old_date,
    )

    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    d30 = await service.get_dashboard(user_id, "30d")
    assert d30["total_views"] == 1000

    d90 = await service.get_dashboard(user_id, "90d")
    assert d90["total_views"] == 1500


async def test_platform_comparison(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", views=1000, likes=50, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="tiktok", views=3000, likes=200, snapshot_date=today,
    )

    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    comparison = await service.get_platform_comparison(user_id, "30d")
    assert len(comparison) == 2
    platforms = [c["platform"] for c in comparison]
    assert "youtube" in platforms
    assert "tiktok" in platforms

    tiktok = next(c for c in comparison if c["platform"] == "tiktok")
    assert tiktok["total_views"] == 3000


async def test_top_posts(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", platform_post_id="vid1",
        views=500, likes=20, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", platform_post_id="vid2",
        views=2000, likes=100, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="tiktok", platform_post_id="tt1",
        views=1500, likes=80, snapshot_date=today,
    )

    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    top = await service.get_top_posts(user_id, "30d", limit=2)
    assert len(top) == 2
    assert top[0]["views"] == 2000
    assert top[0]["platform_post_id"] == "vid2"


async def test_top_posts_sort_by_likes(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", platform_post_id="vid1",
        views=5000, likes=10, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="tiktok", platform_post_id="tt1",
        views=100, likes=500, snapshot_date=today,
    )

    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    top = await service.get_top_posts(
        user_id, "30d", limit=10, sort_by="likes",
    )
    assert top[0]["platform_post_id"] == "tt1"
    assert top[0]["likes"] == 500


async def test_growth(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    yesterday = (
        datetime.now(UTC) - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", followers=1000,
        snapshot_date=yesterday,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", followers=1050,
        snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="tiktok", followers=5000,
        snapshot_date=today,
    )

    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    growth = await service.get_growth(user_id, "7d")
    assert len(growth) == 2
    today_entry = next(g for g in growth if g["date"] == today)
    assert today_entry["followers_by_platform"]["youtube"] == 1050
    assert today_entry["followers_by_platform"]["tiktok"] == 5000


async def test_empty_dashboard(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())

    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    dashboard = await service.get_dashboard(user_id, "30d")
    assert dashboard["total_views"] == 0
    assert dashboard["snapshot_count"] == 0


async def test_collect_unsupported_platform(monkeypatch) -> None:
    from app.services.analytics_service import AnalyticsService

    fake_supabase = FakeSupabase()
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    service = AnalyticsService()
    result = await service.collect_snapshot(
        "u1", "mastodon", {"access_token": "test"},
    )
    assert result == []


# ---------------------------------------------------------------------------
# Worker test
# ---------------------------------------------------------------------------


async def test_analytics_worker(monkeypatch) -> None:
    from app.workers.analytics_worker import collect_all_analytics

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "social_accounts",
        {
            "owner_id": user_id,
            "platform": "youtube",
            "handle": "@test",
            "encrypted_access_token": "tok",
        },
    )

    async def mock_get_analytics(self, post_id, creds):
        return [
            AnalyticsData(
                platform="youtube", views=100, followers=500,
            )
        ]

    from app.adapters.youtube import YouTubeAdapter

    monkeypatch.setattr(YouTubeAdapter, "get_analytics", mock_get_analytics)
    monkeypatch.setattr(
        "app.workers.analytics_worker.get_supabase",
        lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    result = await collect_all_analytics()
    assert result["accounts"] == 1
    assert result["collected"] == 1
    assert result["errors"] == 0


async def test_analytics_worker_handles_errors(monkeypatch) -> None:
    from app.workers.analytics_worker import collect_all_analytics

    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "social_accounts",
        {
            "owner_id": user_id,
            "platform": "youtube",
            "handle": "@test",
            "encrypted_access_token": "tok",
        },
    )

    async def mock_get_analytics_error(self, post_id, creds):
        raise RuntimeError("API down")

    from app.adapters.youtube import YouTubeAdapter

    monkeypatch.setattr(
        YouTubeAdapter, "get_analytics", mock_get_analytics_error,
    )
    monkeypatch.setattr(
        "app.workers.analytics_worker.get_supabase",
        lambda: fake_supabase,
    )
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    result = await collect_all_analytics()
    assert result["errors"] == 1
    assert result["collected"] == 0


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


async def test_api_dashboard(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", views=1000, likes=50, comments=10,
        shares=5, snapshot_date=today,
    )

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/analytics?period=30d")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_views"] == 1000
        assert body["total_likes"] == 50
        assert body["period"] == "30d"


async def test_api_summary(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)

    fake_supabase.insert_row(
        "posts", {"owner_id": user_id, "status": "published"},
    )

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.api.v1.analytics.get_supabase", lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["post_counts"]["published"] == 1


async def test_api_platforms(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", views=1000, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="tiktok", views=2000, snapshot_date=today,
    )

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/analytics/platforms?period=30d")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2


async def test_api_top_posts(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", platform_post_id="vid1",
        views=500, snapshot_date=today,
    )
    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", platform_post_id="vid2",
        views=2000, snapshot_date=today,
    )

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/analytics/top-posts?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["platform_post_id"] == "vid2"


async def test_api_growth(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    user_id, raw_key = _setup_user_and_key(fake_supabase)
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    _insert_snapshot(
        fake_supabase, user_id,
        platform="youtube", followers=1000, snapshot_date=today,
    )

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr(
        "app.services.analytics_service.get_supabase",
        lambda: fake_supabase,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/analytics/growth?period=7d")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert "youtube" in body[0]["followers_by_platform"]


async def test_api_analytics_unauthenticated(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/api/v1/analytics")
        assert resp.status_code == 401


async def test_api_dashboard_is_cached(monkeypatch) -> None:
    from app.main import app

    fake_supabase = FakeSupabase()
    _user_id, raw_key = _setup_user_and_key(fake_supabase)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    calls = {"count": 0}

    async def fake_dashboard(self, owner_id: str, period: str = "30d") -> dict:
        calls["count"] += 1
        return {
            "period": period,
            "days": 30,
            "snapshot_count": 1,
            "total_views": 100,
            "total_likes": 10,
            "total_comments": 1,
            "total_shares": 1,
            "total_impressions": 200,
            "total_reach": 150,
            "engagement_rate": 6.0,
        }

    async def fake_cache_redis():
        return redis

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr("app.core.cache.get_redis", fake_cache_redis)
    monkeypatch.setattr(
        "app.services.analytics_service.AnalyticsService.get_dashboard",
        fake_dashboard,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        first = await client.get("/api/v1/analytics?period=30d")
        second = await client.get("/api/v1/analytics?period=30d")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["total_views"] == 100
    assert calls["count"] == 1
