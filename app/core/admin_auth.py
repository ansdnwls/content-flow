"""Admin authentication via the X-Admin-Key header."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Request, Response, Security
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.core.auth import (
    cache_api_key_id,
    get_cached_api_key_id,
    invalidate_cached_api_key,
    should_update_last_used,
    verify_api_key,
)
from app.core.db import get_supabase
from app.core.errors import AuthenticationError, ForbiddenError

_admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def _touch_last_used(sb, redis, api_key_id: str) -> None:
    settings = get_settings()
    if not await should_update_last_used(
        redis,
        api_key_id,
        min_interval_seconds=settings.api_key_last_used_update_seconds,
    ):
        return

    sb.table("api_keys").update(
        {"last_used_at": datetime.now(UTC).isoformat()},
    ).eq("id", api_key_id).execute()


async def get_admin_user(
    request: Request,
    response: Response = None,
    admin_key: Annotated[str | None, Security(_admin_key_header)] = None,
) -> dict:
    """Authenticate an enterprise admin via X-Admin-Key."""
    if not admin_key:
        raise AuthenticationError("Missing X-Admin-Key header")

    if not admin_key.startswith("cf_admin_"):
        raise AuthenticationError("Invalid admin key format; must start with cf_admin_")

    sb = get_supabase()
    redis = getattr(getattr(request.app, "state", None), "redis", None)
    settings = get_settings()

    row: dict | None = None
    cached_api_key_id = await get_cached_api_key_id(redis, admin_key, namespace="admin")
    if cached_api_key_id:
        row = (
            sb.table("api_keys")
            .select("id, user_id")
            .eq("id", cached_api_key_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
            .data
        )
        if not row:
            await invalidate_cached_api_key(redis, admin_key, namespace="admin")

    if not row:
        result = (
            sb.table("api_keys")
            .select("id, user_id, hashed_key")
            .eq("key_prefix", "cf_admin")
            .eq("is_active", True)
            .execute()
        )

        for candidate in result.data:
            if not verify_api_key(admin_key, candidate["hashed_key"]):
                continue
            row = candidate
            await cache_api_key_id(
                redis,
                admin_key,
                candidate["id"],
                namespace="admin",
                ttl_seconds=settings.api_key_cache_ttl_seconds,
            )
            break

    if not row:
        raise AuthenticationError("Invalid admin key")

    await _touch_last_used(sb, redis, row["id"])

    user_result = (
        sb.table("users")
        .select("id, email, plan")
        .eq("id", row["user_id"])
        .maybe_single()
        .execute()
    )
    user = user_result.data
    if not user:
        raise AuthenticationError("Admin user not found for API key")

    if user["plan"] != "enterprise":
        raise ForbiddenError("Admin access requires enterprise plan")

    request.state.user_id = user["id"]
    request.state.api_key_prefix = "cf_admin"
    request.state.admin_user = user

    from app.api.deps import AuthenticatedUser
    from app.core.rate_limit_dep import enforce_rate_limit

    if response is not None:
        await enforce_rate_limit(
            request,
            response,
            AuthenticatedUser(
                id=user["id"],
                email=user["email"],
                plan=user["plan"],
                is_test_key=False,
            ),
        )
    return user
