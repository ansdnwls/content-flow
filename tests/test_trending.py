"""Tests for Trending Topics API."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from app.services.trending_service import (
    SUPPORTED_PLATFORMS,
    TopicRecommendation,
    TrendItem,
    _cache_key,
    recommend_topics,
)
from tests.fakes import FakeSupabase


def _setup(fake: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row("users", {"id": user_id, "email": "t@x.com", "plan": "build"})
    issued, rec = build_api_key_record(user_id=uuid4(), name="default")
    rec["user_id"] = user_id
    fake.insert_row("api_keys", rec)
    return user_id, issued.raw_key


# ---------------------------------------------------------------------------
# Unit tests — data types
# ---------------------------------------------------------------------------

def test_trend_item_to_dict() -> None:
    item = TrendItem(
        title="AI news", platform="youtube", region="US",
        rank=1, score=0.98, url="https://yt.com/1",
    )
    d = item.to_dict()
    assert d["title"] == "AI news"
    assert d["platform"] == "youtube"
    assert d["score"] == 0.98


def test_topic_recommendation_to_dict() -> None:
    rec = TopicRecommendation(
        topic="AI Agents", score=1.5,
        sources=["youtube", "reddit"],
        related_keywords=["automation"],
    )
    d = rec.to_dict()
    assert d["topic"] == "AI Agents"
    assert len(d["sources"]) == 2


def test_supported_platforms() -> None:
    assert "youtube" in SUPPORTED_PLATFORMS
    assert "reddit" in SUPPORTED_PLATFORMS
    assert "google_trends" in SUPPORTED_PLATFORMS


def test_cache_key_format() -> None:
    key = _cache_key("youtube", "KR", "general")
    assert key == "contentflow:trending:youtube:KR:general"


# ---------------------------------------------------------------------------
# Unit tests — recommend_topics aggregation
# ---------------------------------------------------------------------------

_FAKE_TRENDS = [
    {"title": "Topic A", "platform": "youtube", "region": "US",
     "category": "general", "rank": 1, "url": None, "score": 0.9,
     "metadata": {"channel": "Tech"}},
    {"title": "Topic A", "platform": "reddit", "region": "US",
     "category": "general", "rank": 2, "url": None, "score": 0.8,
     "metadata": {"subreddit": "tech"}},
    {"title": "Topic B", "platform": "youtube", "region": "US",
     "category": "general", "rank": 3, "url": None, "score": 0.5,
     "metadata": {}},
]


async def test_recommend_topics_aggregation() -> None:
    with patch(
        "app.services.trending_service.fetch_trends",
        new_callable=AsyncMock,
        return_value=_FAKE_TRENDS,
    ):
        topics = await recommend_topics(region="US", limit=10)

    assert len(topics) == 2
    # Topic A appears on 2 platforms so should have higher score
    top = topics[0]
    assert top["topic"].lower() == "topic a"
    assert top["score"] == 1.7  # 0.9 + 0.8
    assert "youtube" in top["sources"]
    assert "reddit" in top["sources"]
    assert "Tech" in top["related_keywords"] or "tech" in top["related_keywords"]


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

_MOCK_ITEMS = [
    {"title": "Trend 1", "platform": "youtube", "region": "US",
     "category": "general", "rank": 1, "url": "https://yt.com/1",
     "score": 0.95, "metadata": {}},
    {"title": "Trend 2", "platform": "reddit", "region": "US",
     "category": "general", "rank": 2, "url": "https://reddit.com/2",
     "score": 0.85, "metadata": {"subreddit": "tech"}},
]


async def test_get_trends_endpoint(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup(fake)
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.services.trending_service.get_redis", AsyncMock(return_value=redis))

    async def fake_cache_redis():
        return redis

    monkeypatch.setattr("app.core.cache.get_redis", fake_cache_redis)

    fetch_mock = AsyncMock(return_value=_MOCK_ITEMS)
    with patch("app.api.v1.trending.fetch_trends", fetch_mock):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-API-Key": raw_key},
        ) as client:
            resp = await client.get(
                "/api/v1/trending", params={"region": "US", "limit": "10"},
            )
            second = await client.get(
                "/api/v1/trending", params={"region": "US", "limit": "10"},
            )

    assert resp.status_code == 200
    assert second.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["region"] == "US"
    assert body["data"][0]["title"] == "Trend 1"
    assert fetch_mock.await_count == 1


async def test_get_topics_endpoint(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup(fake)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)

    _MOCK_TOPICS = [
        {"topic": "Trend 1", "score": 0.95, "sources": ["youtube"],
         "related_keywords": []},
        {"topic": "Trend 2", "score": 0.85, "sources": ["reddit"],
         "related_keywords": ["tech"]},
    ]

    with patch(
        "app.api.v1.trending.recommend_topics",
        new_callable=AsyncMock,
        return_value=_MOCK_TOPICS,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-API-Key": raw_key},
        ) as client:
            resp = await client.get(
                "/api/v1/trending/topics", params={"region": "US"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert body["region"] == "US"
    assert body["data"][0]["topic"] in ("Trend 1", "Trend 2")


async def test_generate_from_trend_video(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup(fake)

    queued: list[tuple[str, str]] = []

    class FakeVideoTask:
        @staticmethod
        def delay(video_id: str, owner_id: str) -> None:
            queued.append((video_id, owner_id))

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.trending.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.trending.generate_video_task", FakeVideoTask)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/trending/generate",
            json={
                "topic": "AI Agents",
                "mode": "news",
                "template": "news_brief",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["video_id"] is not None
    assert len(queued) == 1


async def test_generate_from_trend_bomb(monkeypatch) -> None:
    fake = FakeSupabase()
    _, raw_key = _setup(fake)

    bomb_queued: list[tuple[str, str]] = []

    class FakeBombTask:
        @staticmethod
        def delay(bomb_id: str, user_id: str) -> None:
            bomb_queued.append((bomb_id, user_id))

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.trending.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.trending.transform_bomb_task", FakeBombTask)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            "/api/v1/trending/generate",
            json={
                "topic": "AI Agents",
                "mode": "news",
                "platforms": ["youtube", "tiktok"],
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["bomb_id"] is not None
    assert len(bomb_queued) == 1


# ---------------------------------------------------------------------------
# Worker tests
# ---------------------------------------------------------------------------

async def test_refresh_all_trends() -> None:
    with patch(
        "app.services.trending_service.fetch_trends",
        new_callable=AsyncMock,
        return_value=_MOCK_ITEMS,
    ):
        from app.workers.trending_worker import refresh_all_trends

        stats = await refresh_all_trends()

    assert stats["cached_items"] >= 0
    assert stats["errors"] >= 0


def test_celery_beat_schedule() -> None:
    from app.workers.celery_app import celery_app as ca

    schedule = ca.conf.beat_schedule
    assert "refresh-trending-topics-hourly" in schedule
    entry = schedule["refresh-trending-topics-hourly"]
    assert entry["task"] == "contentflow.refresh_trending_topics"
    assert entry["schedule"] == 3600.0


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_trending_snapshots_table_in_schema() -> None:
    from app.models.schemas import SCHEMA_SQL

    assert "trending_snapshots" in SCHEMA_SQL


async def test_save_snapshot(monkeypatch) -> None:
    """Test that save_snapshot writes to the DB."""
    fake = FakeSupabase()
    user_id = str(uuid4())
    fake.insert_row("users", {"id": user_id, "email": "t@x.com", "plan": "free"})
    monkeypatch.setattr("app.core.db.get_supabase", lambda: fake)

    from app.services.trending_service import save_snapshot

    row = await save_snapshot(user_id, "youtube", "US", [{"title": "t1"}])
    assert row["platform"] == "youtube"
    assert row["region"] == "US"
    assert len(fake.tables["trending_snapshots"]) == 1
