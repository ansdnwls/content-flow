"""Analytics API — dashboard, platform comparison, top posts, growth."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.cache import cache
from app.core.db import get_supabase
from app.services.analytics_service import AnalyticsService

router = APIRouter(
    prefix="/analytics", tags=["Analytics"], responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "post_counts": {"published": 32, "scheduled": 4},
                "video_counts": {"completed": 7},
            },
        },
    )

    post_counts: dict[str, int] = Field(
        description="Counts of posts by status.",
    )
    video_counts: dict[str, int] = Field(
        description="Counts of video jobs by status.",
    )


class DashboardResponse(BaseModel):
    period: str
    days: int
    snapshot_count: int
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int
    total_impressions: int
    total_reach: int
    engagement_rate: float


class PlatformMetrics(BaseModel):
    platform: str
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int
    total_impressions: int
    total_reach: int
    engagement_rate: float


class TopPost(BaseModel):
    platform: str
    platform_post_id: str
    views: int
    likes: int
    comments: int
    shares: int
    engagement_rate: float
    snapshot_date: str


class GrowthEntry(BaseModel):
    date: str
    followers_by_platform: dict[str, int]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _count_by_status(table_name: str, owner_id: str) -> dict[str, int]:
    sb = get_supabase()
    result = (
        sb.table(table_name)
        .select("status")
        .eq("owner_id", owner_id)
        .execute()
    )
    counts: dict[str, int] = {}
    for row in result.data:
        status = row["status"]
        counts[status] = counts.get(status, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=DashboardResponse,
    summary="Get Analytics Dashboard",
    description=(
        "Returns aggregated analytics metrics across all platforms "
        "for the specified period (1d, 7d, 30d, 90d)."
    ),
)
@cache(ttl=300, key_prefix="analytics-dashboard")
async def get_analytics_dashboard(
    request: Request,
    response: Response,
    user: CurrentUser,
    period: str = Query("30d", pattern=r"^(1d|7d|30d|90d)$"),
) -> DashboardResponse:
    service = AnalyticsService()
    dashboard = await service.get_dashboard(user.id, period)
    return DashboardResponse(**dashboard)


@router.get(
    "/summary",
    response_model=AnalyticsResponse,
    summary="Get Post/Video Summary",
    description="Returns counts of posts and video jobs by status.",
)
async def get_analytics_summary(user: CurrentUser) -> AnalyticsResponse:
    post_counts = await _count_by_status("posts", user.id)
    video_counts = await _count_by_status("video_jobs", user.id)
    return AnalyticsResponse(
        post_counts=post_counts, video_counts=video_counts,
    )


@router.get(
    "/platforms",
    response_model=list[PlatformMetrics],
    summary="Compare Platform Performance",
    description="Returns per-platform aggregated metrics for comparison.",
)
async def get_platform_comparison(
    user: CurrentUser,
    period: str = Query("30d", pattern=r"^(1d|7d|30d|90d)$"),
) -> list[PlatformMetrics]:
    service = AnalyticsService()
    platforms = await service.get_platform_comparison(user.id, period)
    return [PlatformMetrics(**p) for p in platforms]


@router.get(
    "/top-posts",
    response_model=list[TopPost],
    summary="Get Top Performing Posts",
    description="Returns top posts ranked by the specified metric.",
)
async def get_top_posts(
    user: CurrentUser,
    period: str = Query("30d", pattern=r"^(1d|7d|30d|90d)$"),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("views"),
) -> list[TopPost]:
    service = AnalyticsService()
    posts = await service.get_top_posts(
        user.id, period, limit=limit, sort_by=sort_by,
    )
    return [TopPost(**p) for p in posts]


@router.get(
    "/growth",
    response_model=list[GrowthEntry],
    summary="Get Follower Growth Trends",
    description="Returns daily follower/subscriber counts by platform.",
)
async def get_growth(
    user: CurrentUser,
    period: str = Query("30d", pattern=r"^(1d|7d|30d|90d)$"),
) -> list[GrowthEntry]:
    service = AnalyticsService()
    growth = await service.get_growth(user.id, period)
    return [GrowthEntry(**g) for g in growth]
