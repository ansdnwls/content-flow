"""Platform-specific publish rate limits backed by Redis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from redis.asyncio import Redis

from app.config import get_settings


@dataclass(frozen=True)
class PlatformLimitRule:
    limit: int
    window_seconds: int
    units_per_publish: int = 1


@dataclass(frozen=True)
class PlatformRateLimitDecision:
    allowed: bool
    remaining: int
    limit: int
    units_requested: int
    next_available_at: str | None = None
    retry_after_seconds: int = 0


PLATFORM_LIMITS: dict[str, PlatformLimitRule] = {
    "youtube": PlatformLimitRule(limit=10_000, window_seconds=86_400, units_per_publish=1_600),
    "tiktok": PlatformLimitRule(limit=6, window_seconds=86_400),
    "instagram": PlatformLimitRule(limit=25, window_seconds=86_400),
    "x_twitter": PlatformLimitRule(limit=300, window_seconds=10_800),
    "linkedin": PlatformLimitRule(limit=150, window_seconds=86_400),
}

_redis: Redis | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_entry_cost(member: str) -> int:
    return int(member.rsplit(":", 1)[-1])


def _build_member(cost: int) -> str:
    return f"{int(_utc_now().timestamp())}:{uuid4().hex}:{cost}"


def _window_start(now: datetime, window_seconds: int) -> float:
    return (now - timedelta(seconds=window_seconds)).timestamp()


def _key(platform: str, subject_id: str) -> str:
    return f"contentflow:platform-limit:{platform}:{subject_id}"


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def _subject_id(owner_id: str, social_account_id: str | None) -> str:
    return social_account_id or owner_id


async def check_platform_limit(
    platform: str,
    owner_id: str,
    social_account_id: str | None = None,
    *,
    reserve: bool = False,
) -> PlatformRateLimitDecision:
    rule = PLATFORM_LIMITS.get(platform)
    if rule is None:
        return PlatformRateLimitDecision(
            allowed=True,
            remaining=10**9,
            limit=10**9,
            units_requested=0,
        )

    now = _utc_now()
    redis = await get_redis()
    subject = _subject_id(owner_id, social_account_id)
    key = _key(platform, subject)
    window_start = _window_start(now, rule.window_seconds)

    await redis.zremrangebyscore(key, "-inf", window_start)
    entries = await redis.zrange(key, 0, -1, withscores=True)
    used = sum(_parse_entry_cost(member) for member, _score in entries)
    requested = rule.units_per_publish
    remaining = max(0, rule.limit - used)

    if used + requested <= rule.limit:
        if reserve and requested > 0:
            await redis.zadd(key, {_build_member(requested): now.timestamp()})
            await redis.expire(key, rule.window_seconds)
            remaining = max(0, rule.limit - used - requested)
        return PlatformRateLimitDecision(
            allowed=True,
            remaining=remaining,
            limit=rule.limit,
            units_requested=requested,
        )

    reclaimed = used
    next_available_at: datetime | None = None
    for member, score in entries:
        reclaimed -= _parse_entry_cost(member)
        candidate = datetime.fromtimestamp(score, UTC) + timedelta(seconds=rule.window_seconds)
        if reclaimed + requested <= rule.limit:
            next_available_at = candidate
            break

    if next_available_at is None:
        next_available_at = now + timedelta(seconds=rule.window_seconds)

    retry_after = max(0, int((next_available_at - now).total_seconds()))
    return PlatformRateLimitDecision(
        allowed=False,
        remaining=remaining,
        limit=rule.limit,
        units_requested=requested,
        next_available_at=next_available_at.isoformat(),
        retry_after_seconds=retry_after,
    )
