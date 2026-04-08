"""FastAPI authentication dependencies backed by Supabase."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Header, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from app.config import get_settings
from app.core.auth import (
    cache_api_key_id,
    get_cached_api_key_id,
    invalidate_cached_api_key,
    should_update_last_used,
    verify_api_key,
)
from app.core.db import get_supabase
from app.core.errors import AuthenticationError
from app.core.workspaces import resolve_workspace_id_for_user

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    plan: str
    is_test_key: bool
    api_key_id: str | None = None
    default_workspace_id: str | None = None
    workspace_id: str | None = None


def _parse_prefix(raw_key: str) -> str:
    """Return the API key prefix portion."""
    for prefix in ("cf_live", "cf_test"):
        if raw_key.startswith(f"{prefix}_"):
            return prefix
    raise AuthenticationError(
        "Invalid API key format; must start with cf_live_ or cf_test_",
    )


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


async def get_current_user(
    request: Request,
    api_key: str | None = Security(_api_key_header),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> AuthenticatedUser:
    """Authenticate via X-API-Key against Supabase."""
    if not api_key:
        raise AuthenticationError("Missing X-API-Key header")

    prefix = _parse_prefix(api_key)
    sb = get_supabase()
    redis = getattr(getattr(request.app, "state", None), "redis", None)
    settings = get_settings()

    row: dict | None = None
    cached_api_key_id = await get_cached_api_key_id(redis, api_key, namespace="user")
    if cached_api_key_id:
        row = (
            sb.table("api_keys")
            .select("id, user_id, workspace_id")
            .eq("id", cached_api_key_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
            .data
        )
        if not row:
            await invalidate_cached_api_key(redis, api_key, namespace="user")

    if not row:
        result = (
            sb.table("api_keys")
            .select("id, user_id, hashed_key, workspace_id")
            .eq("key_prefix", prefix)
            .eq("is_active", True)
            .execute()
        )

        for candidate in result.data:
            if not verify_api_key(api_key, candidate["hashed_key"]):
                continue
            row = candidate
            await cache_api_key_id(
                redis,
                api_key,
                candidate["id"],
                namespace="user",
                ttl_seconds=settings.api_key_cache_ttl_seconds,
            )
            break

    if row:
        await _touch_last_used(sb, redis, row["id"])

        user_result = (
            sb.table("users")
            .select("id, email, plan, default_workspace_id")
            .eq("id", row["user_id"])
            .maybe_single()
            .execute()
        )
        user = user_result.data
        if not user:
            raise AuthenticationError("User not found for API key")

        workspace_id = resolve_workspace_id_for_user(
            user["id"],
            requested_workspace_id=x_workspace_id,
            default_workspace_id=user.get("default_workspace_id"),
            api_key_workspace_id=row.get("workspace_id"),
        )

        authenticated = AuthenticatedUser(
            id=user["id"],
            email=user["email"],
            plan=user["plan"],
            is_test_key=prefix == "cf_test",
            api_key_id=row["id"],
            default_workspace_id=user.get("default_workspace_id"),
            workspace_id=workspace_id,
        )
        request.state.user_id = authenticated.id
        request.state.api_key_prefix = prefix
        request.state.workspace_id = authenticated.workspace_id
        request.state.authenticated_user = authenticated
        return authenticated

    raise AuthenticationError("Invalid API key")
