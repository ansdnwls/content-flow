from __future__ import annotations

import math
import time
from dataclasses import dataclass
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import WatchError


@dataclass(slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    reset_after_seconds: int


class SlidingWindowRateLimiter:
    def __init__(
        self,
        redis: Redis,
        *,
        key_prefix: str = "contentflow:rate_limit",
    ) -> None:
        self.redis = redis
        self.key_prefix = key_prefix

    def _key(self, identifier: str) -> str:
        return f"{self.key_prefix}:{identifier}"

    async def check(
        self,
        *,
        identifier: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        key = self._key(identifier)
        now_ms = int(time.time() * 1000)
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

                        return RateLimitResult(
                            allowed=False,
                            limit=limit,
                            remaining=0,
                            retry_after_seconds=retry_after,
                            reset_after_seconds=retry_after,
                        )

                    pipe.multi()
                    pipe.zadd(key, {member: now_ms})
                    pipe.expire(key, window_seconds)
                    await pipe.execute()

                    remaining = max(0, limit - current_count - 1)
                    return RateLimitResult(
                        allowed=True,
                        limit=limit,
                        remaining=remaining,
                        retry_after_seconds=0,
                        reset_after_seconds=window_seconds,
                    )
            except WatchError:
                continue
