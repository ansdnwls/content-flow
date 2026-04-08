"""Redis-backed idempotency cache for webhook deliveries."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError


class IdempotencyStore:
    """Small Redis helper for webhook idempotency lookups."""

    def __init__(self, redis: Redis, ttl_seconds: int = 24 * 60 * 60) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def key_for(webhook_id: str, event_id: str) -> str:
        return f"webhook:idem:{webhook_id}:{event_id}"

    async def store(self, key: str, result: dict[str, Any]) -> bool:
        try:
            await self.redis.set(
                key,
                json.dumps(result, default=str, separators=(",", ":")),
                ex=self.ttl_seconds,
            )
        except (RedisError, TypeError, ValueError):
            return False
        return True

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self.redis.get(key)
        except RedisError:
            return None
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except (JSONDecodeError, TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
