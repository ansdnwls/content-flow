"""Aggregations for the admin dashboard."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from app.core.db import get_supabase
from app.core.response_cache import get_redis

Granularity = Literal["day", "week", "month"]

ADMIN_ANALYTICS_CACHE_TTL_SECONDS = 300
_CACHE_NAMESPACE = "contentflow:response-cache:admin-dashboard"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _range_bounds(
    *,
    start_date: date | None,
    end_date: date | None,
    default_days: int,
) -> tuple[datetime, datetime]:
    end = datetime.combine(end_date or datetime.now(UTC).date(), time.max, tzinfo=UTC)
    start = datetime.combine(
        start_date or (end - timedelta(days=default_days - 1)).date(),
        time.min,
        tzinfo=UTC,
    )
    if start > end:
        start, end = end, start
    return start, end


def _in_range(value: str | None, start: datetime, end: datetime) -> bool:
    parsed = _parse_datetime(value)
    if parsed is None:
        return False
    current = _ensure_utc(parsed)
    return start <= current <= end


def _month_start(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _bucket_start(value: datetime, granularity: Granularity) -> datetime:
    value = value.astimezone(UTC)
    if granularity == "month":
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        start = value - timedelta(days=value.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _bucket_label(value: datetime, granularity: Granularity) -> str:
    start = _bucket_start(value, granularity)
    if granularity == "month":
        return start.strftime("%Y-%m-01")
    return start.date().isoformat()


def _safe_status_code(row: dict[str, Any]) -> int | None:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return None
    status_code = metadata.get("status_code")
    return (
        int(status_code)
        if isinstance(status_code, (int, float, str)) and str(status_code).isdigit()
        else None
    )


def _safe_duration_ms(row: dict[str, Any]) -> float | None:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return None
    duration = metadata.get("duration_ms")
    return float(duration) if isinstance(duration, (int, float)) else None


def _sum_revenue(rows: list[dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        amount = row.get("amount")
        if isinstance(amount, (int, float)):
            total += float(amount)
    return round(total, 2)


def _admin_user_ids(api_keys: list[dict[str, Any]]) -> set[str]:
    return {
        str(row["user_id"])
        for row in api_keys
        if row.get("key_prefix") == "cf_admin" and row.get("user_id")
    }


@dataclass(slots=True)
class AdminAnalyticsService:
    cache_ttl_seconds: int = ADMIN_ANALYTICS_CACHE_TTL_SECONDS

    async def _cached(
        self,
        key_payload: dict[str, Any],
        loader: Callable[[], Awaitable[dict[str, Any] | list[dict[str, Any]]]],
    ) -> dict[str, Any] | list[dict[str, Any]]:
        raw_key = json.dumps(key_payload, sort_keys=True, separators=(",", ":"))
        cache_key = f"{_CACHE_NAMESPACE}:{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()}"
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
        except Exception:
            cached = None
            redis = None
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass

        result = await loader()
        if redis is not None:
            try:
                await redis.set(cache_key, json.dumps(result), ex=self.cache_ttl_seconds)
            except Exception:
                pass
        return result

    async def get_overview(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        start, end = _range_bounds(start_date=start_date, end_date=end_date, default_days=30)

        async def loader() -> dict[str, Any]:
            sb = get_supabase()
            users = sb.table("users").select("*").execute().data
            api_keys = sb.table("api_keys").select("*").execute().data
            payments = sb.table("payments").select("*").execute().data
            posts = sb.table("posts").select("*").execute().data
            videos = sb.table("video_jobs").select("*").execute().data
            audit_logs = sb.table("audit_logs").select("*").execute().data
            admin_user_ids = _admin_user_ids(api_keys)

            dau_cutoff = end - timedelta(days=1)
            mau_cutoff = end - timedelta(days=30)
            active_dau = set()
            active_mau = set()
            for key in api_keys:
                user_id = key.get("user_id")
                last_used_at = key.get("last_used_at")
                if not user_id or not last_used_at:
                    continue
                if _in_range(last_used_at, dau_cutoff, end):
                    active_dau.add(user_id)
                if _in_range(last_used_at, mau_cutoff, end):
                    active_mau.add(user_id)

            month_start = _month_start(end)
            monthly_revenue = _sum_revenue(
                [
                    row
                    for row in payments
                    if _in_range(row.get("created_at"), month_start, end)
                    and row.get("status", "succeeded") == "succeeded"
                ]
            )

            durations = [
                value
                for row in audit_logs
                if _in_range(row.get("created_at"), start, end)
                for value in [_safe_duration_ms(row)]
                if value is not None
            ]
            status_codes = [
                value
                for row in audit_logs
                if _in_range(row.get("created_at"), start, end)
                for value in [_safe_status_code(row)]
                if value is not None
            ]
            total_requests = len(status_codes)
            error_count = len([code for code in status_codes if code >= 500])

            return {
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
                "total_users": len(users),
                "active_users_dau": len(active_dau),
                "active_users_mau": len(active_mau),
                "new_signups": len(
                    [
                        row
                        for row in users
                        if row.get("id") not in admin_user_ids
                        and _in_range(row.get("created_at"), start, end)
                    ]
                ),
                "revenue_this_month": monthly_revenue,
                "total_posts": len(posts),
                "total_videos": len(videos),
                "error_rate": round((error_count / total_requests) * 100, 2)
                if total_requests
                else 0.0,
                "average_response_time_ms": round(sum(durations) / len(durations), 2)
                if durations
                else 0.0,
            }

        return await self._cached(
            {
                "method": "overview",
                "start": start.date().isoformat(),
                "end": end.date().isoformat(),
            },
            loader,
        )

    async def get_growth(
        self,
        *,
        granularity: Granularity = "day",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        start, end = _range_bounds(start_date=start_date, end_date=end_date, default_days=30)

        async def loader() -> dict[str, Any]:
            sb = get_supabase()
            users = sb.table("users").select("*").execute().data
            api_keys = sb.table("api_keys").select("*").execute().data
            payments = sb.table("payments").select("*").execute().data
            posts = sb.table("posts").select("*").execute().data
            videos = sb.table("video_jobs").select("*").execute().data
            audit_logs = sb.table("audit_logs").select("*").execute().data
            admin_user_ids = _admin_user_ids(api_keys)

            points: dict[str, dict[str, Any]] = {}

            def ensure_bucket(label: str) -> dict[str, Any]:
                return points.setdefault(
                    label,
                    {
                        "bucket": label,
                        "signups": 0,
                        "revenue": 0.0,
                        "api_calls": 0,
                        "posts": 0,
                        "videos": 0,
                    },
                )

            for row in users:
                created = _parse_datetime(row.get("created_at"))
                if (
                    row.get("id") not in admin_user_ids
                    and created
                    and start <= _ensure_utc(created) <= end
                ):
                    ensure_bucket(_bucket_label(created, granularity))["signups"] += 1

            for row in payments:
                created = _parse_datetime(row.get("created_at"))
                if created and start <= _ensure_utc(created) <= end:
                    ensure_bucket(_bucket_label(created, granularity))["revenue"] += float(
                        row.get("amount", 0) or 0
                    )

            for row in posts:
                created = _parse_datetime(row.get("created_at"))
                if created and start <= _ensure_utc(created) <= end:
                    ensure_bucket(_bucket_label(created, granularity))["posts"] += 1

            for row in videos:
                created = _parse_datetime(row.get("created_at"))
                if created and start <= _ensure_utc(created) <= end:
                    ensure_bucket(_bucket_label(created, granularity))["videos"] += 1

            for row in audit_logs:
                created = _parse_datetime(row.get("created_at"))
                if not created or not (start <= _ensure_utc(created) <= end):
                    continue
                if row.get("action", "").startswith("admin."):
                    continue
                ensure_bucket(_bucket_label(created, granularity))["api_calls"] += 1

            return {
                "granularity": granularity,
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
                "points": [
                    {
                        **value,
                        "revenue": round(value["revenue"], 2),
                    }
                    for _, value in sorted(points.items())
                ],
            }

        return await self._cached(
            {
                "method": "growth",
                "granularity": granularity,
                "start": start.date().isoformat(),
                "end": end.date().isoformat(),
            },
            loader,
        )

    async def get_top_users(
        self,
        *,
        limit: int = 50,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        start, end = _range_bounds(start_date=start_date, end_date=end_date, default_days=30)

        async def loader() -> dict[str, Any]:
            sb = get_supabase()
            users = sb.table("users").select("*").execute().data
            api_keys = sb.table("api_keys").select("*").execute().data
            posts = sb.table("posts").select("*").execute().data
            videos = sb.table("video_jobs").select("*").execute().data
            audit_logs = sb.table("audit_logs").select("*").execute().data
            admin_user_ids = _admin_user_ids(api_keys)

            by_user: dict[str, dict[str, Any]] = {
                row["id"]: {
                    "user_id": row["id"],
                    "email": row.get("email"),
                    "plan": row.get("plan", "free"),
                    "api_calls": 0,
                    "posts": 0,
                    "videos": 0,
                }
                for row in users
                if row.get("id") not in admin_user_ids
            }

            for row in posts:
                owner_id = row.get("owner_id")
                if owner_id in by_user and _in_range(row.get("created_at"), start, end):
                    by_user[owner_id]["posts"] += 1

            for row in videos:
                owner_id = row.get("owner_id")
                if owner_id in by_user and _in_range(row.get("created_at"), start, end):
                    by_user[owner_id]["videos"] += 1

            for row in audit_logs:
                user_id = row.get("user_id")
                if user_id in by_user and _in_range(row.get("created_at"), start, end):
                    if row.get("action", "").startswith("admin."):
                        continue
                    by_user[user_id]["api_calls"] += 1

            ranked = []
            for item in by_user.values():
                item["total_usage"] = item["api_calls"] + item["posts"] + item["videos"]
                if item["total_usage"] > 0:
                    ranked.append(item)

            ranked.sort(
                key=lambda row: (
                    row["total_usage"],
                    row["api_calls"],
                    row["posts"],
                    row["videos"],
                    row["email"] or "",
                ),
                reverse=True,
            )

            return {
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
                "users": ranked[:limit],
            }

        return await self._cached(
            {
                "method": "top-users",
                "limit": limit,
                "start": start.date().isoformat(),
                "end": end.date().isoformat(),
            },
            loader,
        )

    async def get_churn_risk(
        self,
        *,
        limit: int = 50,
        inactivity_days: int = 7,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        _, end = _range_bounds(start_date=None, end_date=end_date, default_days=30)
        current_start = end - timedelta(days=inactivity_days)
        previous_start = current_start - timedelta(days=inactivity_days)

        async def loader() -> dict[str, Any]:
            sb = get_supabase()
            users = sb.table("users").select("*").execute().data
            api_keys = sb.table("api_keys").select("*").execute().data
            posts = sb.table("posts").select("*").execute().data
            videos = sb.table("video_jobs").select("*").execute().data
            audit_logs = sb.table("audit_logs").select("*").execute().data
            admin_user_ids = _admin_user_ids(api_keys)

            last_seen_by_user: dict[str, datetime] = {}
            for row in api_keys:
                user_id = row.get("user_id")
                parsed = _parse_datetime(row.get("last_used_at"))
                if not user_id or not parsed:
                    continue
                current = _ensure_utc(parsed)
                previous = last_seen_by_user.get(user_id)
                if previous is None or current > previous:
                    last_seen_by_user[user_id] = current

            current_activity = defaultdict(int)
            previous_activity = defaultdict(int)

            def add_activity(rows: list[dict[str, Any]], owner_key: str) -> None:
                for row in rows:
                    owner_id = row.get(owner_key)
                    created = _parse_datetime(row.get("created_at"))
                    if not owner_id or not created:
                        continue
                    current = _ensure_utc(created)
                    if current_start <= current <= end:
                        current_activity[owner_id] += 1
                    elif previous_start <= current < current_start:
                        previous_activity[owner_id] += 1

            add_activity(posts, "owner_id")
            add_activity(videos, "owner_id")

            for row in audit_logs:
                user_id = row.get("user_id")
                created = _parse_datetime(row.get("created_at"))
                if not user_id or not created or row.get("action", "").startswith("admin."):
                    continue
                current = _ensure_utc(created)
                if current_start <= current <= end:
                    current_activity[user_id] += 1
                elif previous_start <= current < current_start:
                    previous_activity[user_id] += 1

            users_at_risk = []
            for row in users:
                user_id = row["id"]
                if user_id in admin_user_ids:
                    continue
                last_seen = last_seen_by_user.get(user_id)
                days_inactive = (
                    (end - last_seen).days if last_seen is not None else inactivity_days + 1
                )
                current_total = current_activity[user_id]
                previous_total = previous_activity[user_id]
                usage_drop_ratio = (
                    round(1 - (current_total / previous_total), 2) if previous_total > 0 else 0.0
                )

                reasons: list[str] = []
                risk_score = 0
                if days_inactive >= inactivity_days:
                    reasons.append("inactive")
                    risk_score += min(days_inactive, 30)
                if previous_total > 0 and current_total <= previous_total / 2:
                    reasons.append("usage_drop")
                    risk_score += int(usage_drop_ratio * 100)

                if not reasons:
                    continue

                users_at_risk.append(
                    {
                        "user_id": user_id,
                        "email": row.get("email"),
                        "plan": row.get("plan", "free"),
                        "last_seen_at": last_seen.isoformat() if last_seen else None,
                        "days_inactive": days_inactive,
                        "current_period_usage": current_total,
                        "previous_period_usage": previous_total,
                        "usage_drop_ratio": usage_drop_ratio,
                        "risk_score": risk_score,
                        "reasons": reasons,
                    }
                )

            users_at_risk.sort(
                key=lambda row: (
                    row["risk_score"],
                    row["days_inactive"],
                    row["usage_drop_ratio"],
                ),
                reverse=True,
            )
            return {
                "period_end": end.date().isoformat(),
                "inactivity_days": inactivity_days,
                "users": users_at_risk[:limit],
            }

        return await self._cached(
            {
                "method": "churn",
                "limit": limit,
                "inactivity_days": inactivity_days,
                "end": end.date().isoformat(),
            },
            loader,
        )
