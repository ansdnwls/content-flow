"""Billing / plan-limit checks and usage tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.db import get_supabase
from app.core.errors import BillingLimitError

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"posts_per_month": 20, "video_gen_per_month": 3, "social_sets": 2},
    "build": {"posts_per_month": 200, "video_gen_per_month": 20, "social_sets": 5},
    "scale": {"posts_per_month": 999_999, "video_gen_per_month": 100, "social_sets": 20},
    "enterprise": {
        "posts_per_month": 999_999,
        "video_gen_per_month": 999_999,
        "social_sets": 999_999,
    },
}

RATE_LIMITS: dict[str, int] = {
    "free": 10,
    "build": 60,
    "scale": 300,
    "enterprise": 1000,
}

RATE_WINDOW_SECONDS = 60


def get_rate_limit(plan: str) -> int:
    """Return requests-per-minute limit for a plan."""
    return RATE_LIMITS.get(plan, RATE_LIMITS["free"])


def get_plan_limits(plan: str) -> dict[str, int]:
    """Return monthly limits for a plan."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


def _month_start_iso() -> str:
    """Return the first day of the current month as ISO string."""
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


async def count_posts_this_month(owner_id: str, workspace_id: str | None = None) -> int:
    """Count posts created this month for the owner."""
    sb = get_supabase()
    query = sb.table("posts").select("id", count="exact").eq("owner_id", owner_id)
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    result = query.execute()
    return result.count or 0


async def count_videos_this_month(owner_id: str, workspace_id: str | None = None) -> int:
    """Count video jobs created this month for the owner."""
    sb = get_supabase()
    query = sb.table("video_jobs").select("id", count="exact").eq("owner_id", owner_id)
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    result = query.execute()
    return result.count or 0


async def check_post_limit_bulk(
    owner_id: str,
    plan: str,
    count: int,
    *,
    workspace_id: str | None = None,
) -> int:
    """Return remaining post quota. Raise BillingLimitError when quota is 0."""
    limits = get_plan_limits(plan)
    used = await count_posts_this_month(owner_id, workspace_id)
    remaining = max(0, limits["posts_per_month"] - used)
    if remaining == 0:
        raise BillingLimitError(
            f"Monthly post limit reached ({limits['posts_per_month']}). "
            "Upgrade your plan for more posts."
        )
    return remaining


async def check_post_limit(owner_id: str, plan: str, *, workspace_id: str | None = None) -> None:
    """Raise BillingLimitError if owner exceeded monthly post quota."""
    limits = get_plan_limits(plan)
    used = await count_posts_this_month(owner_id, workspace_id)
    if used >= limits["posts_per_month"]:
        raise BillingLimitError(
            f"Monthly post limit reached ({limits['posts_per_month']}). "
            "Upgrade your plan for more posts."
        )


async def check_video_limit(
    owner_id: str,
    plan: str,
    *,
    workspace_id: str | None = None,
) -> None:
    """Raise BillingLimitError if owner exceeded monthly video-gen quota."""
    limits = get_plan_limits(plan)
    used = await count_videos_this_month(owner_id, workspace_id)
    if used >= limits["video_gen_per_month"]:
        raise BillingLimitError(
            f"Monthly video generation limit reached ({limits['video_gen_per_month']}). "
            "Upgrade your plan for more video generations."
        )


async def get_usage_summary(owner_id: str, plan: str, workspace_id: str | None = None) -> dict:
    """Return current month usage summary."""
    limits = get_plan_limits(plan)
    posts_used = await count_posts_this_month(owner_id, workspace_id)
    videos_used = await count_videos_this_month(owner_id, workspace_id)

    sb = get_supabase()
    accounts_query = (
        sb.table("social_accounts")
        .select("id", count="exact")
        .eq("owner_id", owner_id)
    )
    if workspace_id is not None:
        accounts_query = accounts_query.eq("workspace_id", workspace_id)
    accounts_result = accounts_query.execute()
    accounts_used = accounts_result.count or 0

    return {
        "plan": plan,
        "posts_used": posts_used,
        "posts_limit": limits["posts_per_month"],
        "videos_used": videos_used,
        "videos_limit": limits["video_gen_per_month"],
        "accounts_used": accounts_used,
        "accounts_limit": limits["social_sets"],
        "rate_limit_per_minute": get_rate_limit(plan),
    }


async def get_usage_history(
    owner_id: str,
    days: int = 30,
    workspace_id: str | None = None,
) -> list[dict]:
    """Return daily usage counts for the last N days."""
    sb = get_supabase()

    posts_query = sb.table("posts").select("created_at").eq("owner_id", owner_id)
    videos_query = sb.table("video_jobs").select("created_at").eq("owner_id", owner_id)
    if workspace_id is not None:
        posts_query = posts_query.eq("workspace_id", workspace_id)
        videos_query = videos_query.eq("workspace_id", workspace_id)
    posts = posts_query.execute().data
    videos = videos_query.execute().data

    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    daily: dict[str, dict[str, int]] = {}
    for i in range(days):
        day = today - timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        daily[key] = {"posts": 0, "videos": 0}

    for post in posts:
        created = post.get("created_at", "")[:10]
        if created in daily:
            daily[created]["posts"] += 1

    for video in videos:
        created = video.get("created_at", "")[:10]
        if created in daily:
            daily[created]["videos"] += 1

    return [
        {"date": date, **counts}
        for date, counts in sorted(daily.items())
    ]
