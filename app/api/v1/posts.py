"""Posts API — create / list / get / cancel posts across multiple platforms."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.billing import check_post_limit
from app.core.db import get_supabase
from app.core.errors import NotFoundError

router = APIRouter(prefix="/posts", tags=["Posts"])


# ── Request / Response schemas ────────────────────────────────────

class CreatePostRequest(BaseModel):
    text: str | None = None
    platforms: list[str] = Field(..., min_length=1)
    media_urls: list[str] = Field(default_factory=list)
    media_type: str | None = None
    scheduled_for: datetime | None = None
    platform_options: dict = Field(default_factory=dict)


class PlatformStatus(BaseModel):
    status: str = "pending"
    platform_post_id: str | None = None


class PostResponse(BaseModel):
    id: str
    status: str
    text: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    media_type: str | None = None
    scheduled_for: datetime | None = None
    platforms: dict[str, PlatformStatus] = Field(default_factory=dict)
    is_test: bool = False
    created_at: datetime
    updated_at: datetime


class PostListResponse(BaseModel):
    data: list[PostResponse]
    total: int
    page: int
    limit: int


# ── Helper functions (Supabase CRUD) ─────────────────────────────

def _determine_status(scheduled_for: datetime | None) -> str:
    return "scheduled" if scheduled_for else "pending"


async def _create_post_record(
    user: AuthenticatedUser,
    req: CreatePostRequest,
) -> dict:
    """Insert a post row + post_platforms rows into Supabase."""
    sb = get_supabase()
    status = _determine_status(req.scheduled_for)

    post_data = {
        "user_id": user.id,
        "text": req.text,
        "media_urls": req.media_urls,
        "media_type": req.media_type,
        "status": status,
        "scheduled_for": req.scheduled_for.isoformat() if req.scheduled_for else None,
        "platform_options": req.platform_options,
        "is_test": user.is_test_key,
    }

    result = sb.table("posts").insert(post_data).execute()
    post = result.data[0]

    # Create per-platform rows
    platform_rows = [
        {"post_id": post["id"], "platform": p, "status": "pending"}
        for p in req.platforms
    ]
    sb.table("post_platforms").insert(platform_rows).execute()

    return post


async def _get_post(post_id: str, user_id: str) -> dict:
    """Fetch a single post with its platform statuses."""
    sb = get_supabase()

    result = (
        sb.table("posts")
        .select("*")
        .eq("id", post_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise NotFoundError("Post", post_id)

    # Fetch platform statuses
    platforms_result = (
        sb.table("post_platforms")
        .select("platform, status, platform_post_id")
        .eq("post_id", post_id)
        .execute()
    )

    post = result.data
    post["_platforms"] = {
        row["platform"]: {
            "status": row["status"],
            "platform_post_id": row.get("platform_post_id"),
        }
        for row in platforms_result.data
    }
    return post


async def _list_posts(
    user_id: str, *, page: int = 1, limit: int = 20, status: str | None = None
) -> tuple[list[dict], int]:
    """List posts with pagination. Returns (posts, total_count)."""
    sb = get_supabase()

    query = sb.table("posts").select("*", count="exact").eq("user_id", user_id)
    if status:
        query = query.eq("status", status)

    query = query.order("created_at", desc=True)
    offset = (page - 1) * limit
    query = query.range(offset, offset + limit - 1)

    result = query.execute()

    # Fetch platform statuses for all posts
    post_ids = [p["id"] for p in result.data]
    platforms_map: dict[str, dict] = {}
    if post_ids:
        pp_result = (
            sb.table("post_platforms")
            .select("post_id, platform, status, platform_post_id")
            .in_("post_id", post_ids)
            .execute()
        )
        for row in pp_result.data:
            platforms_map.setdefault(row["post_id"], {})[row["platform"]] = {
                "status": row["status"],
                "platform_post_id": row.get("platform_post_id"),
            }

    for post in result.data:
        post["_platforms"] = platforms_map.get(post["id"], {})

    return result.data, result.count or 0


async def _cancel_post(post_id: str, user_id: str) -> dict:
    """Cancel a scheduled/pending post."""
    post = await _get_post(post_id, user_id)

    if post["status"] not in ("pending", "scheduled"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel post with status '{post['status']}'",
        )

    sb = get_supabase()
    sb.table("posts").update({"status": "cancelled"}).eq("id", post_id).execute()
    sb.table("post_platforms").update({"status": "failed"}).eq("post_id", post_id).execute()

    post["status"] = "cancelled"
    return post


def _to_response(post: dict) -> PostResponse:
    """Convert a raw DB row (with _platforms) to PostResponse."""
    platforms_raw = post.pop("_platforms", {})
    platforms = {
        k: PlatformStatus(status=v["status"], platform_post_id=v.get("platform_post_id"))
        for k, v in platforms_raw.items()
    }
    return PostResponse(
        id=post["id"],
        status=post["status"],
        text=post.get("text"),
        media_urls=post.get("media_urls") or [],
        media_type=post.get("media_type"),
        scheduled_for=post.get("scheduled_for"),
        platforms=platforms,
        is_test=post.get("is_test", False),
        created_at=post["created_at"],
        updated_at=post["updated_at"],
    )


# ── Routes ────────────────────────────────────────────────────────

@router.post("", response_model=PostResponse, status_code=201)
async def create_post(
    req: CreatePostRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    await check_post_limit(user)
    post = await _create_post_record(user, req)
    return _to_response(await _get_post(post["id"], user.id))


@router.get("", response_model=PostListResponse)
async def list_posts(
    user: AuthenticatedUser = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    posts, total = await _list_posts(user.id, page=page, limit=limit, status=status)
    return PostListResponse(
        data=[_to_response(p) for p in posts],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
):
    post = await _get_post(str(post_id), user.id)
    return _to_response(post)


@router.delete("/{post_id}", response_model=PostResponse)
async def cancel_post(
    post_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
):
    post = await _cancel_post(str(post_id), user.id)
    return _to_response(post)
