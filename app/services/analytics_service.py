"""Analytics engine — collect, aggregate, and compare platform metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.adapters.base import PlatformAdapter
from app.core.cache import invalidate_user_cache
from app.core.db import get_supabase

ADAPTER_MAP: dict[str, type[PlatformAdapter]] = {}


def _get_adapter_map() -> dict[str, type[PlatformAdapter]]:
    """Lazy-load adapter map to avoid circular imports."""
    if not ADAPTER_MAP:
        from app.adapters.instagram import InstagramAdapter
        from app.adapters.tiktok import TikTokAdapter
        from app.adapters.youtube import YouTubeAdapter

        ADAPTER_MAP.update(
            {
                "youtube": YouTubeAdapter,
                "tiktok": TikTokAdapter,
                "instagram": InstagramAdapter,
            }
        )
    return ADAPTER_MAP


class AnalyticsService:
    """Collects and aggregates analytics across platforms."""

    async def collect_snapshot(
        self,
        owner_id: str,
        platform: str,
        credentials: dict[str, str],
        platform_post_id: str | None = None,
    ) -> list[dict]:
        """Fetch analytics from adapter and store as snapshot."""
        adapters = _get_adapter_map()
        adapter_cls = adapters.get(platform)
        if not adapter_cls:
            return []

        adapter = adapter_cls()
        try:
            analytics_list = await adapter.get_analytics(
                platform_post_id, credentials,
            )
        except NotImplementedError:
            return []

        sb = get_supabase()
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        stored: list[dict] = []

        for data in analytics_list:
            row = {
                "owner_id": owner_id,
                "platform": data.platform,
                "platform_post_id": data.platform_post_id,
                "snapshot_date": today,
                "views": data.views,
                "likes": data.likes,
                "comments": data.comments,
                "shares": data.shares,
                "followers": data.followers,
                "impressions": data.impressions,
                "reach": data.reach,
                "engagement_rate": data.engagement_rate,
            }
            result = (
                sb.table("analytics_snapshots")
                .upsert(
                    row,
                    on_conflict="owner_id,platform,platform_post_id,snapshot_date",
                )
                .execute()
            )
            stored.extend(result.data)

        if stored:
            await invalidate_user_cache(owner_id, prefixes=["analytics-dashboard"])

        return stored

    async def get_dashboard(
        self,
        owner_id: str,
        period: str = "30d",
    ) -> dict:
        """Return aggregated dashboard metrics for the given period."""
        days = _parse_period(period)
        cutoff = (
            datetime.now(UTC) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        sb = get_supabase()
        snapshots = (
            sb.table("analytics_snapshots")
            .select("*")
            .eq("owner_id", owner_id)
            .execute()
            .data
        )

        filtered = [
            s for s in snapshots
            if s.get("snapshot_date", "") >= cutoff
        ]

        totals = _aggregate(filtered)
        totals["period"] = period
        totals["days"] = days
        totals["snapshot_count"] = len(filtered)
        return totals

    async def get_platform_comparison(
        self,
        owner_id: str,
        period: str = "30d",
    ) -> list[dict]:
        """Return per-platform aggregated metrics."""
        days = _parse_period(period)
        cutoff = (
            datetime.now(UTC) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        sb = get_supabase()
        snapshots = (
            sb.table("analytics_snapshots")
            .select("*")
            .eq("owner_id", owner_id)
            .execute()
            .data
        )

        filtered = [
            s for s in snapshots
            if s.get("snapshot_date", "") >= cutoff
        ]

        by_platform: dict[str, list[dict]] = {}
        for s in filtered:
            platform = s.get("platform", "unknown")
            by_platform.setdefault(platform, []).append(s)

        results = []
        for platform, items in sorted(by_platform.items()):
            agg = _aggregate(items)
            agg["platform"] = platform
            results.append(agg)

        return results

    async def get_top_posts(
        self,
        owner_id: str,
        period: str = "30d",
        limit: int = 10,
        sort_by: str = "views",
    ) -> list[dict]:
        """Return top-performing posts ranked by a metric."""
        days = _parse_period(period)
        cutoff = (
            datetime.now(UTC) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        sb = get_supabase()
        snapshots = (
            sb.table("analytics_snapshots")
            .select("*")
            .eq("owner_id", owner_id)
            .execute()
            .data
        )

        # Only post-level snapshots (has platform_post_id)
        post_snapshots = [
            s for s in snapshots
            if s.get("platform_post_id")
            and s.get("snapshot_date", "") >= cutoff
        ]

        # Group by post and take the latest snapshot per post
        latest_by_post: dict[str, dict] = {}
        for s in post_snapshots:
            key = f"{s['platform']}:{s['platform_post_id']}"
            existing = latest_by_post.get(key)
            if not existing or s.get(
                "snapshot_date", "",
            ) > existing.get("snapshot_date", ""):
                latest_by_post[key] = s

        posts = list(latest_by_post.values())

        valid_sort = sort_by if sort_by in (
            "views", "likes", "comments", "shares", "engagement_rate",
        ) else "views"
        posts.sort(key=lambda p: p.get(valid_sort, 0), reverse=True)

        return [
            {
                "platform": p["platform"],
                "platform_post_id": p["platform_post_id"],
                "views": p.get("views", 0),
                "likes": p.get("likes", 0),
                "comments": p.get("comments", 0),
                "shares": p.get("shares", 0),
                "engagement_rate": float(p.get("engagement_rate", 0)),
                "snapshot_date": p.get("snapshot_date", ""),
            }
            for p in posts[:limit]
        ]

    async def get_growth(
        self,
        owner_id: str,
        period: str = "30d",
    ) -> list[dict]:
        """Return daily follower/subscriber growth trends."""
        days = _parse_period(period)
        cutoff = (
            datetime.now(UTC) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        sb = get_supabase()
        snapshots = (
            sb.table("analytics_snapshots")
            .select("*")
            .eq("owner_id", owner_id)
            .execute()
            .data
        )

        # Account-level snapshots only (no platform_post_id)
        account_snapshots = [
            s for s in snapshots
            if not s.get("platform_post_id")
            and s.get("snapshot_date", "") >= cutoff
        ]

        # Group by date + platform
        by_date: dict[str, dict[str, int]] = {}
        for s in account_snapshots:
            date = s.get("snapshot_date", "")
            platform = s.get("platform", "unknown")
            by_date.setdefault(date, {})[platform] = s.get("followers", 0)

        return [
            {"date": date, "followers_by_platform": platforms}
            for date, platforms in sorted(by_date.items())
        ]


def _parse_period(period: str) -> int:
    """Convert period string like '7d', '30d', '90d' to days."""
    mapping = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    return mapping.get(period, 30)


def _aggregate(snapshots: list[dict]) -> dict:
    """Sum up metrics across snapshots."""
    total_views = sum(s.get("views", 0) for s in snapshots)
    total_likes = sum(s.get("likes", 0) for s in snapshots)
    total_comments = sum(s.get("comments", 0) for s in snapshots)
    total_shares = sum(s.get("shares", 0) for s in snapshots)
    total_impressions = sum(s.get("impressions", 0) for s in snapshots)
    total_reach = sum(s.get("reach", 0) for s in snapshots)

    denominator = total_impressions if total_impressions > 0 else (
        total_views if total_views > 0 else 1
    )
    engagement_rate = round(
        (total_likes + total_comments + total_shares) / denominator * 100,
        2,
    )

    return {
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_impressions": total_impressions,
        "total_reach": total_reach,
        "engagement_rate": engagement_rate,
    }
