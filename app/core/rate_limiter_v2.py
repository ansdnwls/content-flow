from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import WatchError

if TYPE_CHECKING:
    from app.api.deps import AuthenticatedUser

PLAN_LIMITS_PER_HOUR: dict[str, int] = {
    "free": 100,
    "build": 1000,
    "scale": 10_000,
    "enterprise": 50_000,
}

HEAVY_ENDPOINT_LIMITS: dict[tuple[str, str], int] = {
    ("POST", "/api/v1/videos/generate"): 10,
}

RATE_LIMIT_WINDOW_SECONDS = 3600
WARNING_RATIO = 0.8


@dataclass(slots=True, frozen=True)
class RateLimitPolicy:
    name: str
    limit: int
    window_seconds: int
    scope: str


@dataclass(slots=True)
class RateLimitResultV2:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    reset_after_seconds: int
    used: int
    warning: str | None = None
    scope: str = "global"


class SlidingWindowRateLimiterV2:
    def __init__(
        self,
        redis: Redis,
        *,
        key_prefix: str = "contentflow:rate_limit:v2",
        now_fn=time.time,
    ) -> None:
        self.redis = redis
        self.key_prefix = key_prefix
        self.now_fn = now_fn

    def _key(self, identifier: str, scope: str) -> str:
        return f"{self.key_prefix}:{scope}:{identifier}"

    async def check(
        self,
        *,
        identifier: str,
        limit: int,
        window_seconds: int,
        scope: str = "global",
    ) -> RateLimitResultV2:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        key = self._key(identifier, scope)
        now_ms = int(self.now_fn() * 1000)
        window_ms = window_seconds * 1000
        window_start = now_ms - window_ms
        member = f"{now_ms}:{uuid4().hex}"

        while True:
            try:
                async with self.redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(key)
                    await pipe.zremrangebyscore(key, 0, window_start)
                    current_count = await pipe.zcard(key)

                    if current_count >= limit:
                        oldest = await pipe.zrange(key, 0, 0, withscores=True)
                        await pipe.reset()
                        retry_after = 1
                        if oldest:
                            oldest_score = int(oldest[0][1])
                            retry_after = max(
                                1,
                                math.ceil((oldest_score + window_ms - now_ms) / 1000),
                            )
                        return RateLimitResultV2(
                            allowed=False,
                            limit=limit,
                            remaining=0,
                            retry_after_seconds=retry_after,
                            reset_after_seconds=retry_after,
                            used=current_count,
                            scope=scope,
                        )

                    pipe.multi()
                    pipe.zadd(key, {member: now_ms})
                    pipe.expire(key, window_seconds)
                    await pipe.execute()

                    used = current_count + 1
                    remaining = max(0, limit - used)
                    warning = None
                    if used / limit >= WARNING_RATIO:
                        warning = (
                            f"{scope} quota at {math.floor(used / limit * 100)}% "
                            f"({used}/{limit})"
                        )

                    return RateLimitResultV2(
                        allowed=True,
                        limit=limit,
                        remaining=remaining,
                        retry_after_seconds=0,
                        reset_after_seconds=window_seconds,
                        used=used,
                        warning=warning,
                        scope=scope,
                    )
            except WatchError:
                continue


def get_hourly_plan_limit(plan: str) -> int:
    return PLAN_LIMITS_PER_HOUR.get(plan, PLAN_LIMITS_PER_HOUR["free"])


def get_rate_limit_policies(
    user: AuthenticatedUser,
    *,
    method: str,
    path: str,
) -> list[RateLimitPolicy]:
    policies = [
        RateLimitPolicy(
            name="global",
            limit=get_hourly_plan_limit(user.plan),
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            scope="global",
        )
    ]
    heavy_limit = HEAVY_ENDPOINT_LIMITS.get((method.upper(), path))
    if heavy_limit is not None:
        policies.append(
            RateLimitPolicy(
                name="heavy",
                limit=heavy_limit,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
                scope="heavy",
            )
        )
    return policies
