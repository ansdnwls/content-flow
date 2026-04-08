"""Trending Topics API — real-time trend discovery and content generation."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.cache import cache, invalidate_user_cache
from app.core.db import get_supabase
from app.services.trending_service import (
    SUPPORTED_PLATFORMS,
    SUPPORTED_REGIONS,
    fetch_trends,
    recommend_topics,
)
from app.workers.bomb_worker import transform_bomb_task
from app.workers.video_worker import generate_video_task

router = APIRouter(
    prefix="/trending", tags=["Trending"], responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TrendItemResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "AI Agents Are Taking Over",
                "platform": "youtube",
                "region": "US",
                "category": "general",
                "rank": 1,
                "url": "https://www.youtube.com/watch?v=abc",
                "score": 0.98,
                "metadata": {"channel": "Tech Daily"},
            },
        },
    )

    title: str
    platform: str
    region: str
    category: str = "general"
    rank: int = 0
    url: str | None = None
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrendListResponse(BaseModel):
    data: list[TrendItemResponse]
    total: int
    platforms: list[str]
    region: str


class TopicRecommendationResponse(BaseModel):
    topic: str
    score: float
    sources: list[str]
    related_keywords: list[str]


class TopicListResponse(BaseModel):
    data: list[TopicRecommendationResponse]
    total: int
    region: str


class GenerateFromTrendRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "AI Agents Are Taking Over",
                "mode": "news",
                "template": "news_brief",
                "language": "en",
                "platforms": ["youtube", "tiktok"],
            },
        },
    )

    topic: str
    mode: str = "general"
    template: str | None = None
    language: str = "en"
    format: str = "shorts"
    platforms: list[str] = Field(default_factory=list)


class GenerateFromTrendResponse(BaseModel):
    video_id: str | None = None
    bomb_id: str | None = None
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=TrendListResponse,
    summary="Get Trending Topics",
    description=(
        "Returns trending topics across platforms, "
        "optionally filtered by platform, region, and category."
    ),
)
@cache(ttl=1800, key_prefix="trending-list")
async def get_trends(
    user: CurrentUser,
    platform: str | None = Query(
        default=None,
        description=f"Filter by platform: {', '.join(SUPPORTED_PLATFORMS)}",
    ),
    region: str = Query(
        default="US",
        description=f"Region code: {', '.join(SUPPORTED_REGIONS)}",
    ),
    category: str = Query(default="general"),
    limit: int = Query(default=20, ge=1, le=100),
) -> TrendListResponse:
    items = await fetch_trends(
        platform=platform, region=region, category=category, limit=limit,
    )
    platforms_used = list({i["platform"] for i in items})
    return TrendListResponse(
        data=[TrendItemResponse(**i) for i in items],
        total=len(items),
        platforms=platforms_used,
        region=region,
    )


@router.get(
    "/topics",
    response_model=TopicListResponse,
    summary="Get Topic Recommendations",
    description=(
        "Aggregates trends across platforms and returns scored topic "
        "recommendations with source attribution and related keywords."
    ),
)
async def get_topic_recommendations(
    user: CurrentUser,
    region: str = Query(default="US"),
    category: str = Query(default="general"),
    limit: int = Query(default=10, ge=1, le=50),
) -> TopicListResponse:
    topics = await recommend_topics(
        region=region, category=category, limit=limit,
    )
    return TopicListResponse(
        data=[TopicRecommendationResponse(**t) for t in topics],
        total=len(topics),
        region=region,
    )


@router.post(
    "/generate",
    response_model=GenerateFromTrendResponse,
    status_code=201,
    summary="Generate Content from Trend",
    description=(
        "Creates a video generation job or content bomb from a trending topic. "
        "If platforms are specified, creates a bomb; otherwise generates a video."
    ),
)
async def generate_from_trend(
    req: GenerateFromTrendRequest,
    user: CurrentUser,
) -> GenerateFromTrendResponse:
    sb = get_supabase()

    if req.platforms:
        bomb = (
            sb.table("bombs")
            .insert({
                "user_id": user.id,
                "topic": req.topic,
                "status": "queued",
                "platform_contents": {},
            })
            .execute()
        )
        bomb_row = bomb.data[0]
        transform_bomb_task.delay(bomb_row["id"], user.id)
        await invalidate_user_cache(user.id)
        return GenerateFromTrendResponse(
            bomb_id=bomb_row["id"], status="queued",
        )

    video = (
        sb.table("video_jobs")
        .insert({
            "owner_id": user.id,
            "topic": req.topic,
            "mode": req.mode,
            "language": req.language,
            "format": req.format,
            "template": req.template,
            "status": "queued",
            "auto_publish": {},
        })
        .execute()
    )
    video_row = video.data[0]
    generate_video_task.delay(video_row["id"], user.id)
    await invalidate_user_cache(user.id)
    return GenerateFromTrendResponse(
        video_id=video_row["id"], status="queued",
    )
