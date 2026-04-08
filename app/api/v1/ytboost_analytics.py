"""YtBoost analytics dashboard API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES
from app.core.cache import cache
from app.core.db import get_supabase

router = APIRouter(
    prefix="/ytboost/analytics",
    tags=["YtBoost Analytics"],
    responses=COMMON_RESPONSES,
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ChannelOverviewStats(BaseModel):
    youtube_channel_id: str
    channel_name: str | None = None
    shorts_extracted: int = 0
    shorts_published: int = 0
    comments_replied: int = 0


class OverviewResponse(BaseModel):
    this_month: OverviewThisMonth
    channels: list[ChannelOverviewStats] = Field(default_factory=list)


class OverviewThisMonth(BaseModel):
    shorts_extracted: int = 0
    shorts_published: int = 0
    comments_replied: int = 0


# Re-declare OverviewResponse after OverviewThisMonth is defined
OverviewResponse.model_rebuild()


class PlatformPerformance(BaseModel):
    platform: str
    count: int = 0
    avg_views: int = 0
    avg_likes: int = 0


class ShortsPerformanceResponse(BaseModel):
    total_shorts: int = 0
    platforms: list[PlatformPerformance] = Field(default_factory=list)


class CommentStatsResponse(BaseModel):
    total_comments: int = 0
    auto_replied: int = 0
    manual_replied: int = 0
    pending: int = 0
    auto_ratio: float = 0.0
    avg_response_seconds: float | None = None


class ChannelHealthItem(BaseModel):
    id: str
    youtube_channel_id: str
    channel_name: str | None = None
    auto_distribute: bool = False
    auto_comment_mode: str = "review"
    last_checked_at: str | None = None
    shorts_count: int = 0
    status: str = "active"


class ChannelHealthResponse(BaseModel):
    channels: list[ChannelHealthItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_start() -> str:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="YtBoost Monthly Overview",
)
@cache(ttl=300, key_prefix="ytboost-analytics-overview")
async def get_overview(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> OverviewResponse:
    """Aggregate this-month stats: shorts extracted/published, comments replied."""
    sb = get_supabase()
    month_start = _month_start()

    subscriptions = (
        sb.table("ytboost_subscriptions")
        .select("youtube_channel_id, channel_name")
        .eq("user_id", user.id)
        .execute()
        .data
    )

    shorts = (
        sb.table("ytboost_shorts")
        .select("source_channel_id, status, created_at")
        .eq("user_id", user.id)
        .gte("created_at", month_start)
        .execute()
        .data
    )

    comments = (
        sb.table("comments")
        .select("reply_status, created_at")
        .eq("user_id", user.id)
        .eq("platform", "youtube")
        .eq("reply_status", "replied")
        .gte("created_at", month_start)
        .execute()
        .data
    )

    total_extracted = len(shorts)
    total_published = sum(
        1 for s in shorts if s.get("status") in ("approved", "distributed")
    )
    total_replied = len(comments)

    channel_stats: dict[str, ChannelOverviewStats] = {}
    for sub in subscriptions:
        cid = sub["youtube_channel_id"]
        channel_stats[cid] = ChannelOverviewStats(
            youtube_channel_id=cid,
            channel_name=sub.get("channel_name"),
        )

    for short in shorts:
        cid = short.get("source_channel_id", "")
        if cid in channel_stats:
            channel_stats[cid].shorts_extracted += 1
            if short.get("status") in ("approved", "distributed"):
                channel_stats[cid].shorts_published += 1

    return OverviewResponse(
        this_month=OverviewThisMonth(
            shorts_extracted=total_extracted,
            shorts_published=total_published,
            comments_replied=total_replied,
        ),
        channels=list(channel_stats.values()),
    )


@router.get(
    "/shorts-performance",
    response_model=ShortsPerformanceResponse,
    summary="Shorts Platform Performance",
)
@cache(ttl=300, key_prefix="ytboost-analytics-shorts-performance")
async def get_shorts_performance(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> ShortsPerformanceResponse:
    """Per-platform distribution stats for extracted shorts."""
    sb = get_supabase()

    shorts = (
        sb.table("ytboost_shorts")
        .select("id, status")
        .eq("user_id", user.id)
        .execute()
        .data
    )
    short_ids = [s["id"] for s in shorts]
    if not short_ids:
        return ShortsPerformanceResponse(total_shorts=0, platforms=[])

    deliveries = (
        sb.table("post_deliveries")
        .select("platform, status, metadata")
        .eq("owner_id", user.id)
        .execute()
        .data
    )

    platform_agg: dict[str, dict] = {}
    for d in deliveries:
        plat = d.get("platform", "unknown")
        if plat not in platform_agg:
            platform_agg[plat] = {"count": 0, "total_views": 0, "total_likes": 0}
        platform_agg[plat]["count"] += 1
        meta = d.get("metadata") or {}
        platform_agg[plat]["total_views"] += meta.get("views", 0)
        platform_agg[plat]["total_likes"] += meta.get("likes", 0)

    platforms = []
    for plat, agg in sorted(platform_agg.items()):
        count = agg["count"]
        platforms.append(
            PlatformPerformance(
                platform=plat,
                count=count,
                avg_views=agg["total_views"] // count if count else 0,
                avg_likes=agg["total_likes"] // count if count else 0,
            )
        )

    return ShortsPerformanceResponse(
        total_shorts=len(shorts),
        platforms=platforms,
    )


@router.get(
    "/comment-stats",
    response_model=CommentStatsResponse,
    summary="Comment Reply Statistics",
)
@cache(ttl=300, key_prefix="ytboost-analytics-comment-stats")
async def get_comment_stats(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> CommentStatsResponse:
    """Auto vs manual reply ratio, average response time."""
    sb = get_supabase()

    comments = (
        sb.table("comments")
        .select("reply_status, created_at, updated_at")
        .eq("user_id", user.id)
        .eq("platform", "youtube")
        .execute()
        .data
    )

    total = len(comments)
    auto_replied = 0
    manual_replied = 0
    pending = 0
    response_times: list[float] = []

    for c in comments:
        status = c.get("reply_status", "")
        if status == "replied":
            auto_replied += 1
            created = c.get("created_at", "")
            updated = c.get("updated_at", "")
            if created and updated and created != updated:
                try:
                    t_created = datetime.fromisoformat(created)
                    t_updated = datetime.fromisoformat(updated)
                    diff = (t_updated - t_created).total_seconds()
                    if diff > 0:
                        response_times.append(diff)
                except (ValueError, TypeError):
                    pass
        elif status == "review_pending":
            manual_replied += 1
        elif status == "pending":
            pending += 1

    auto_ratio = auto_replied / total if total else 0.0
    avg_response = (
        round(sum(response_times) / len(response_times), 2)
        if response_times
        else None
    )

    return CommentStatsResponse(
        total_comments=total,
        auto_replied=auto_replied,
        manual_replied=manual_replied,
        pending=pending,
        auto_ratio=round(auto_ratio, 4),
        avg_response_seconds=avg_response,
    )


@router.get(
    "/channel-health",
    response_model=ChannelHealthResponse,
    summary="Channel Health Status",
)
@cache(ttl=300, key_prefix="ytboost-analytics-channel-health")
async def get_channel_health(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> ChannelHealthResponse:
    """Health status for each connected YouTube channel."""
    sb = get_supabase()

    subscriptions = (
        sb.table("ytboost_subscriptions")
        .select("*")
        .eq("user_id", user.id)
        .execute()
        .data
    )

    shorts = (
        sb.table("ytboost_shorts")
        .select("source_channel_id")
        .eq("user_id", user.id)
        .execute()
        .data
    )
    shorts_by_channel: dict[str, int] = {}
    for s in shorts:
        cid = s.get("source_channel_id", "")
        shorts_by_channel[cid] = shorts_by_channel.get(cid, 0) + 1

    stale_threshold = (datetime.now(UTC) - timedelta(days=7)).isoformat()

    channels = []
    for sub in subscriptions:
        cid = sub["youtube_channel_id"]
        last_checked = sub.get("last_checked_at")
        status = "active"
        if not last_checked or last_checked < stale_threshold:
            status = "stale"

        channels.append(
            ChannelHealthItem(
                id=sub["id"],
                youtube_channel_id=cid,
                channel_name=sub.get("channel_name"),
                auto_distribute=sub.get("auto_distribute", False),
                auto_comment_mode=sub.get("auto_comment_mode", "review"),
                last_checked_at=last_checked,
                shorts_count=shorts_by_channel.get(cid, 0),
                status=status,
            )
        )

    return ChannelHealthResponse(channels=channels)
