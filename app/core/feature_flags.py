"""Redis-backed feature flag storage and evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

FeatureFlagType = Literal["boolean", "percentage", "user_list", "plan_based"]
PlanName = Literal["free", "build", "scale", "enterprise"]

FEATURE_FLAG_NAMESPACE = "contentflow:feature-flags"
FEATURE_FLAG_INDEX_KEY = f"{FEATURE_FLAG_NAMESPACE}:index"

PLAN_ORDER: dict[str, int] = {
    "free": 0,
    "build": 1,
    "scale": 2,
    "enterprise": 3,
}


class FeatureFlagError(RuntimeError):
    """Base feature flag error."""


class FeatureFlagNotFoundError(FeatureFlagError):
    """Raised when a flag does not exist in Redis or defaults."""


class FeatureFlagNameConflictError(FeatureFlagError):
    """Raised when attempting to create a flag with an existing name."""


class FeatureFlagStorageError(FeatureFlagError):
    """Raised when a Redis write fails."""


class FeatureFlag(BaseModel):
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{1,62}$")
    type: FeatureFlagType
    enabled: bool = True
    default_enabled: bool = False
    description: str | None = None
    percentage: int | None = Field(default=None, ge=0, le=100)
    user_ids: list[str] = Field(default_factory=list)
    required_plan: PlanName | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_configuration(self) -> FeatureFlag:
        if self.type == "boolean":
            return self
        if self.type == "percentage" and self.percentage is None:
            raise ValueError("percentage flags require a percentage value")
        if self.type == "user_list":
            self.user_ids = sorted(set(self.user_ids))
        if self.type == "plan_based" and self.required_plan is None:
            raise ValueError("plan_based flags require a required_plan value")
        return self


DEFAULT_FEATURE_FLAGS: dict[str, FeatureFlag] = {
    "new_dashboard_ui": FeatureFlag(
        name="new_dashboard_ui",
        type="percentage",
        percentage=10,
        description="Roll out the redesigned dashboard UI to a subset of users.",
    ),
    "shopsync_coupang_live": FeatureFlag(
        name="shopsync_coupang_live",
        type="user_list",
        description="Allowlisted users can access live Coupang syncing.",
    ),
    "ytboost_ai_thumbnails": FeatureFlag(
        name="ytboost_ai_thumbnails",
        type="plan_based",
        required_plan="scale",
        description="Enable AI thumbnail generation for scale and enterprise plans.",
    ),
    "ko_beta_features": FeatureFlag(
        name="ko_beta_features",
        type="user_list",
        description="Allowlisted Korean beta cohort features.",
    ),
}


def feature_flag_key(name: str) -> str:
    return f"{FEATURE_FLAG_NAMESPACE}:{name}"


class FeatureFlagStore:
    """Feature flag persistence and evaluation with process-local caching."""

    _cache: ClassVar[dict[str, FeatureFlag | None]] = {}

    def __init__(self, redis: Any | None = None) -> None:
        self.redis = redis

    @classmethod
    def clear_local_cache(cls) -> None:
        cls._cache.clear()

    @classmethod
    def invalidate_local_cache(cls, name: str) -> None:
        cls._cache.pop(name, None)

    def _default_flag(self, name: str) -> FeatureFlag | None:
        default_flag = DEFAULT_FEATURE_FLAGS.get(name)
        return default_flag.model_copy(deep=True) if default_flag is not None else None

    async def get_flag(self, name: str) -> FeatureFlag | None:
        cached = self._cache.get(name)
        if cached is not None or name in self._cache:
            return cached.model_copy(deep=True) if cached is not None else None

        default_flag = self._default_flag(name)
        if self.redis is None:
            self._cache[name] = default_flag
            return default_flag.model_copy(deep=True) if default_flag is not None else None

        try:
            raw = await self.redis.get(feature_flag_key(name))
        except Exception:
            self._cache[name] = default_flag
            return default_flag.model_copy(deep=True) if default_flag is not None else None

        if not raw:
            self._cache[name] = default_flag
            return default_flag.model_copy(deep=True) if default_flag is not None else None

        try:
            flag = FeatureFlag.model_validate_json(raw)
        except Exception:
            self._cache[name] = default_flag
            return default_flag.model_copy(deep=True) if default_flag is not None else None

        self._cache[name] = flag
        return flag.model_copy(deep=True)

    async def list_flags(self) -> list[FeatureFlag]:
        names = set(DEFAULT_FEATURE_FLAGS)
        if self.redis is not None:
            try:
                names.update(await self.redis.smembers(FEATURE_FLAG_INDEX_KEY))
            except Exception:
                pass

        flags: list[FeatureFlag] = []
        for name in sorted(names):
            flag = await self.get_flag(name)
            if flag is not None:
                flags.append(flag)
        return flags

    async def create_flag(self, flag: FeatureFlag) -> FeatureFlag:
        if await self.get_flag(flag.name) is not None:
            raise FeatureFlagNameConflictError(flag.name)
        redis = self._require_redis()
        now = datetime.now(UTC)
        stored = flag.model_copy(update={"created_at": now, "updated_at": now})
        await self._write_flag(redis, stored)
        return stored

    async def update_flag(self, name: str, patch: Mapping[str, Any]) -> FeatureFlag:
        existing = await self.get_flag(name)
        if existing is None:
            raise FeatureFlagNotFoundError(name)

        redis = self._require_redis()
        payload = existing.model_dump()
        payload.update(dict(patch))
        payload["name"] = name
        payload["created_at"] = existing.created_at
        payload["updated_at"] = datetime.now(UTC)
        updated = FeatureFlag.model_validate(payload)
        await self._write_flag(redis, updated)
        return updated

    async def delete_flag(self, name: str) -> FeatureFlag | None:
        existing = await self.get_flag(name)
        if existing is None:
            raise FeatureFlagNotFoundError(name)

        redis = self._require_redis()
        try:
            await redis.delete(feature_flag_key(name))
            await redis.srem(FEATURE_FLAG_INDEX_KEY, name)
        except Exception as exc:
            raise FeatureFlagStorageError(name) from exc

        self.invalidate_local_cache(name)
        return await self.get_flag(name)

    async def is_enabled(
        self,
        flag_name: str,
        user_id: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        flag = await self.get_flag(flag_name)
        if flag is None:
            return False
        try:
            return self.evaluate(flag, user_id=user_id, context=context)
        except Exception:
            return flag.default_enabled

    def evaluate(
        self,
        flag: FeatureFlag,
        *,
        user_id: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        context = context or {}

        if flag.type == "boolean":
            return flag.enabled

        if not flag.enabled:
            return False

        if flag.type == "percentage":
            if flag.percentage is None or flag.percentage <= 0:
                return False
            if flag.percentage >= 100:
                return True
            rollout_key = user_id or str(context.get("rollout_key") or "")
            if not rollout_key:
                return flag.default_enabled
            bucket = self._bucket(flag.name, rollout_key)
            return bucket < flag.percentage

        if flag.type == "user_list":
            return bool(user_id and user_id in set(flag.user_ids))

        if flag.type == "plan_based":
            current_plan = str(context.get("plan", "free")).lower()
            current_rank = PLAN_ORDER.get(current_plan, -1)
            required_rank = PLAN_ORDER.get(flag.required_plan or "enterprise", 99)
            return current_rank >= required_rank

        return flag.default_enabled

    @staticmethod
    def _bucket(flag_name: str, rollout_key: str) -> int:
        digest = hashlib.sha256(f"{flag_name}:{rollout_key}".encode()).hexdigest()
        return int(digest, 16) % 100

    def _require_redis(self) -> Any:
        if self.redis is None:
            raise FeatureFlagStorageError("redis unavailable")
        return self.redis

    async def _write_flag(self, redis: Any, flag: FeatureFlag) -> None:
        try:
            await redis.set(feature_flag_key(flag.name), flag.model_dump_json())
            await redis.sadd(FEATURE_FLAG_INDEX_KEY, flag.name)
        except Exception as exc:
            raise FeatureFlagStorageError(flag.name) from exc
        self.invalidate_local_cache(flag.name)
