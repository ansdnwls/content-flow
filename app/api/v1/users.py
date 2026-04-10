"""User profile and preferences endpoints."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.core.cache import cache
from app.core.db import get_supabase
from app.core.i18n import SUPPORTED_LOCALES

_current_user = Depends(get_current_user)

router = APIRouter(prefix="/users", tags=["users"])


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    plan: str
    language: str = "ko"
    timezone: str = "Asia/Seoul"


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=5)
    timezone: str | None = Field(default=None, max_length=50)


def _validate_timezone(value: str) -> str:
    """Return a valid IANA timezone or raise a 422 for unsupported values."""
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Unsupported timezone") from exc
    return value


def _load_profile(user: AuthenticatedUser) -> UserProfile:
    sb = get_supabase()
    response = (
        sb.table("users")
        .select("id, email, full_name, plan, language, timezone")
        .eq("id", user.id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    result = rows[0] if rows else None
    if not result:
        return UserProfile(id=user.id, email=user.email, plan=user.plan)
    return UserProfile(**result)


@router.get("/me", response_model=UserProfile)
@cache(ttl=60, key_prefix="users-me")
async def get_me(
    request: Request,
    response: Response,
    user: AuthenticatedUser = _current_user,
):
    """Get the current user's profile."""
    return _load_profile(user)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    body: UpdateUserRequest,
    user: AuthenticatedUser = _current_user,
):
    """Update the current user's profile (name, language, timezone)."""
    updates: dict = {}
    if body.full_name is not None:
        updates["full_name"] = body.full_name
    if body.language is not None:
        if body.language not in SUPPORTED_LOCALES:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported language. Supported: {', '.join(SUPPORTED_LOCALES)}",
            )
        updates["language"] = body.language
    if body.timezone is not None:
        updates["timezone"] = _validate_timezone(body.timezone)

    if not updates:
        return _load_profile(user)

    sb = get_supabase()
    result = (
        sb.table("users")
        .update(updates)
        .eq("id", user.id)
        .execute()
    )
    row = result.data[0] if result.data else {}
    return UserProfile(
        id=user.id,
        email=row.get("email", user.email),
        full_name=row.get("full_name"),
        plan=row.get("plan", user.plan),
        language=row.get("language", "ko"),
        timezone=row.get("timezone", "Asia/Seoul"),
    )
