"""Trending topics service — collect, cache, and score platform trends."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from redis.asyncio import Redis

from app.config import get_settings

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

SUPPORTED_PLATFORMS = ("youtube", "reddit", "google_trends")
SUPPORTED_REGIONS = ("US", "KR", "JP")
CACHE_TTL_SECONDS = 1800  # 30 minutes


@dataclass(frozen=True)
class TrendItem:
    """A single trending topic from a platform."""

    title: str
    platform: str
    region: str
    category: str = "general"
    rank: int = 0
    url: str | None = None
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "platform": self.platform,
            "region": self.region,
            "category": self.category,
            "rank": self.rank,
            "url": self.url,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class TopicRecommendation:
    """An aggregated topic recommendation scored across sources."""

    topic: str
    score: float
    sources: list[str]
    related_keywords: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "score": self.score,
            "sources": self.sources,
            "related_keywords": self.related_keywords,
        }


# ---------------------------------------------------------------------------
# Redis cache helpers
# ---------------------------------------------------------------------------

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            get_settings().redis_url, decode_responses=True,
        )
    return _redis


def reset_redis_client() -> None:
    global _redis
    _redis = None


def _cache_key(platform: str, region: str, category: str) -> str:
    return f"contentflow:trending:{platform}:{region}:{category}"


async def _get_cached(
    redis: Redis, platform: str, region: str, category: str,
) -> list[dict] | None:
    raw = await redis.get(_cache_key(platform, region, category))
    if raw is None:
        return None
    return json.loads(raw)


async def _set_cached(
    redis: Redis,
    platform: str,
    region: str,
    category: str,
    items: list[dict],
) -> None:
    key = _cache_key(platform, region, category)
    await redis.set(key, json.dumps(items), ex=CACHE_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Platform collectors
# ---------------------------------------------------------------------------

async def _fetch_youtube_trends(
    region: str, category: str, limit: int,
) -> list[TrendItem]:
    """Fetch trending videos from YouTube Data API v3."""
    settings = get_settings()
    api_key = settings.youtube_api_key
    if not api_key:
        return []

    params: dict[str, Any] = {
        "part": "snippet",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": min(limit, 50),
        "key": api_key,
    }
    if category and category != "general":
        params["videoCategoryId"] = category

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/videos", params=params,
        )
        if resp.status_code != 200:
            return []

        items: list[TrendItem] = []
        for i, item in enumerate(resp.json().get("items", [])):
            snippet = item.get("snippet", {})
            items.append(TrendItem(
                title=snippet.get("title", ""),
                platform="youtube",
                region=region,
                category=category,
                rank=i + 1,
                url=f"https://www.youtube.com/watch?v={item['id']}",
                score=round(1.0 - i * 0.02, 2),
                metadata={
                    "channel": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                },
            ))
        return items


async def _fetch_reddit_trends(
    region: str, category: str, limit: int,
) -> list[TrendItem]:
    """Fetch trending posts from Reddit /r/popular."""
    headers = {"User-Agent": "ContentFlow/1.0"}
    subreddit = "popular"
    if category and category != "general":
        subreddit = category

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json",
            params={"limit": min(limit, 25), "geo_filter": region},
            headers=headers,
        )
        if resp.status_code != 200:
            return []

        items: list[TrendItem] = []
        for i, child in enumerate(resp.json().get("data", {}).get("children", [])):
            post = child.get("data", {})
            items.append(TrendItem(
                title=post.get("title", ""),
                platform="reddit",
                region=region,
                category=category,
                rank=i + 1,
                url=f"https://reddit.com{post.get('permalink', '')}",
                score=round(1.0 - i * 0.04, 2),
                metadata={
                    "subreddit": post.get("subreddit", ""),
                    "ups": post.get("ups", 0),
                    "num_comments": post.get("num_comments", 0),
                },
            ))
        return items


async def _fetch_google_trends(
    region: str, _category: str, limit: int,
) -> list[TrendItem]:
    """Fetch daily trending searches from Google Trends RSS."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://trends.google.com/trending/rss",
            params={"geo": region},
        )
        if resp.status_code != 200:
            return []

        # Simple XML title extraction (no lxml dependency)
        import re

        titles = re.findall(r"<title>(.+?)</title>", resp.text)
        # Skip the first title (feed title)
        titles = [t for t in titles[1:] if t.strip()][:limit]

        return [
            TrendItem(
                title=t,
                platform="google_trends",
                region=region,
                category="general",
                rank=i + 1,
                score=round(1.0 - i * 0.05, 2),
            )
            for i, t in enumerate(titles)
        ]


_COLLECTORS = {
    "youtube": _fetch_youtube_trends,
    "reddit": _fetch_reddit_trends,
    "google_trends": _fetch_google_trends,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_trends(
    *,
    platform: str | None = None,
    region: str = "US",
    category: str = "general",
    limit: int = 20,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Fetch trending topics, optionally filtered by platform/region/category."""
    platforms = [platform] if platform else list(SUPPORTED_PLATFORMS)
    redis = await get_redis()
    all_items: list[dict[str, Any]] = []

    for plat in platforms:
        collector = _COLLECTORS.get(plat)
        if not collector:
            continue

        if use_cache:
            cached = await _get_cached(redis, plat, region, category)
            if cached is not None:
                all_items.extend(cached[:limit])
                continue

        items = await collector(region, category, limit)
        dicts = [item.to_dict() for item in items]

        if dicts:
            await _set_cached(redis, plat, region, category, dicts)

        all_items.extend(dicts[:limit])

    # Sort by score descending, limit total
    all_items.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_items[:limit]


async def recommend_topics(
    *,
    region: str = "US",
    category: str = "general",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Aggregate trends across platforms and produce scored recommendations."""
    trends = await fetch_trends(region=region, category=category, limit=50)

    # Group by normalized title
    topic_map: dict[str, dict[str, Any]] = {}
    for t in trends:
        key = t["title"].lower().strip()
        if key not in topic_map:
            topic_map[key] = {
                "topic": t["title"],
                "score": 0.0,
                "sources": [],
                "related_keywords": [],
            }
        entry = topic_map[key]
        entry["score"] = round(entry["score"] + t.get("score", 0), 2)
        source = t["platform"]
        if source not in entry["sources"]:
            entry["sources"].append(source)

        # Extract related keywords from metadata
        meta = t.get("metadata", {})
        for field_name in ("subreddit", "channel"):
            val = meta.get(field_name)
            if val and val not in entry["related_keywords"]:
                entry["related_keywords"].append(val)

    recommendations = sorted(
        topic_map.values(), key=lambda x: x["score"], reverse=True,
    )
    return recommendations[:limit]


async def save_snapshot(
    owner_id: str,
    platform: str,
    region: str,
    items: list[dict],
) -> dict:
    """Persist a trending snapshot to the database."""
    from app.core.db import get_supabase

    sb = get_supabase()
    result = (
        sb.table("trending_snapshots")
        .insert({
            "owner_id": owner_id,
            "platform": platform,
            "region": region,
            "items": items,
            "fetched_at": datetime.now(UTC).isoformat(),
        })
        .execute()
    )
    return result.data[0]
