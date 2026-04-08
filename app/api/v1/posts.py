"""Posts API: create, list, fetch, cancel, and enqueue post jobs."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, CONFLICT_ERROR, NOT_FOUND_ERROR
from app.core.billing import check_post_limit_bulk
from app.core.cache import invalidate_user_cache
from app.core.db import get_supabase
from app.core.errors import BillingLimitError, NotFoundError
from app.services.post_service import bulk_enqueue
from app.services.throttle import compute_throttle_offsets
from app.services.usage_alerts import send_usage_alerts_if_needed
from app.workers.post_worker import publish_post_task

router = APIRouter(prefix="/posts", tags=["Posts"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class CreatePostRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "New legal explainer is live.",
                "platforms": ["youtube", "tiktok", "instagram"],
                "media_urls": ["https://cdn.example.com/video.mp4"],
                "media_type": "video",
                "scheduled_for": "2026-04-07T09:00:00+09:00",
                "platform_options": {
                    "youtube": {"title": "DUI 3-strike explained", "privacy": "public"},
                    "tiktok": {"title": "DUI 3-strike explained #law"},
                },
            },
        },
    )

    text: str | None = Field(default=None, max_length=10000)
    platforms: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Platforms to publish to.",
    )
    media_urls: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="Media assets to attach.",
    )
    media_type: str = Field(
        default="text",
        max_length=50,
        description="Type of content attached to the post.",
    )
    scheduled_for: datetime | None = Field(
        default=None,
        description="Schedule timestamp in ISO 8601. Omit for immediate publishing.",
    )
    platform_options: dict = Field(
        default_factory=dict,
        description="Per-platform publish options such as title, caption, or privacy.",
    )


class PlatformStatus(BaseModel):
    status: str = "pending"
    platform_post_id: str | None = None


class PostResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "post_123",
                "status": "scheduled",
                "text": "New legal explainer is live.",
                "media_urls": ["https://cdn.example.com/video.mp4"],
                "media_type": "video",
                "scheduled_for": "2026-04-07T09:00:00+09:00",
                "platforms": {
                    "youtube": {"status": "pending", "platform_post_id": None},
                    "tiktok": {"status": "pending", "platform_post_id": None},
                },
                "created_at": "2026-04-06T21:20:00+00:00",
                "updated_at": "2026-04-06T21:20:00+00:00",
            },
        },
    )

    id: str
    status: str
    text: str | None = None
    media_urls: list[str] = Field(default_factory=list)
    media_type: str = "text"
    scheduled_for: datetime | None = None
    platforms: dict[str, PlatformStatus] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PostListResponse(BaseModel):
    data: list[PostResponse]
    total: int
    page: int
    limit: int


class DryRunDeliveryPreview(BaseModel):
    platform: str
    social_account_id: str | None = None
    status: str = "validated"


class DryRunPostResponse(BaseModel):
    dry_run: bool = True
    validated: bool = True
    will_enqueue: bool
    media_type: str
    scheduled_for: datetime | None = None
    platforms: list[str]
    missing_accounts: list[str] = Field(default_factory=list)
    expected_deliveries: list[DryRunDeliveryPreview] = Field(default_factory=list)
    platform_options: dict = Field(default_factory=dict)


class BulkCreatePostRequest(BaseModel):
    posts: list[CreatePostRequest] = Field(..., min_length=1, max_length=100)
    mode: Literal["all_or_nothing", "partial"] = "all_or_nothing"


class BulkPostItemResult(BaseModel):
    index: int
    status: Literal["created", "failed"]
    post: PostResponse | None = None
    error: str | None = None


class BulkPostResponse(BaseModel):
    total_submitted: int
    total_created: int
    total_failed: int
    results: list[BulkPostItemResult]


def _determine_status(scheduled_for: datetime | None) -> str:
    return "scheduled" if scheduled_for else "pending"


def _resolve_delivery_accounts(
    owner_id: str,
    platforms: list[str],
    workspace_id: str | None,
) -> dict[str, str]:
    """Map each platform to the newest connected social account for this owner."""
    if not platforms:
        return {}

    sb = get_supabase()
    query = (
        sb.table("social_accounts")
        .select("id, platform")
        .eq("owner_id", owner_id)
        .in_("platform", platforms)
    )
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    rows = query.order("created_at", desc=True).execute().data

    accounts: dict[str, str] = {}
    for row in rows:
        accounts.setdefault(row["platform"], row["id"])
    return accounts


async def _create_post_record(
    owner_id: str,
    req: CreatePostRequest,
    *,
    workspace_id: str | None,
    api_key_id: str | None,
) -> dict:
    """Insert a post row and related post delivery rows into Supabase."""
    sb = get_supabase()
    status = _determine_status(req.scheduled_for)
    social_accounts = _resolve_delivery_accounts(owner_id, req.platforms, workspace_id)

    post_data = {
        "owner_id": owner_id,
        "workspace_id": workspace_id,
        "api_key_id": api_key_id,
        "text": req.text,
        "media_urls": req.media_urls,
        "media_type": req.media_type,
        "status": status,
        "scheduled_for": req.scheduled_for.isoformat() if req.scheduled_for else None,
        "platform_options": req.platform_options,
    }
    inserted_post = sb.table("posts").insert(post_data).execute().data[0]

    delivery_rows = [
        {
            "post_id": inserted_post["id"],
            "owner_id": owner_id,
            "platform": platform,
            "status": "pending",
            "social_account_id": social_accounts.get(platform),
        }
        for platform in req.platforms
    ]
    sb.table("post_deliveries").insert(delivery_rows).execute()

    return inserted_post


async def _get_post(post_id: str, owner_id: str, workspace_id: str | None) -> dict:
    """Fetch a single post and its per-platform statuses from Supabase."""
    sb = get_supabase()

    query = sb.table("posts").select("*").eq("id", post_id).eq("owner_id", owner_id)
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    post_result = query.maybe_single().execute()
    post = post_result.data
    if not post:
        raise NotFoundError("Post", post_id)

    deliveries = (
        sb.table("post_deliveries")
        .select("platform, status, platform_post_id")
        .eq("post_id", post_id)
        .execute()
        .data
    )
    post["_platforms"] = {
        row["platform"]: {
            "status": row["status"],
            "platform_post_id": row.get("platform_post_id"),
        }
        for row in deliveries
    }
    return post


async def _list_posts(
    owner_id: str,
    workspace_id: str | None,
    *,
    page: int = 1,
    limit: int = 20,
    status_filter: str | None = None,
) -> tuple[list[dict], int]:
    """List posts with pagination. Returns (posts, total_count)."""
    sb = get_supabase()

    query = (
        sb.table("posts")
        .select("*, post_deliveries(*)", count="exact")
        .eq("owner_id", owner_id)
    )
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    if status_filter:
        query = query.eq("status", status_filter)

    offset = (page - 1) * limit
    result = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    posts = result.data
    for post in posts:
        deliveries = post.pop("post_deliveries", []) or []
        post["_platforms"] = {
            row["platform"]: {
                "status": row["status"],
                "platform_post_id": row.get("platform_post_id"),
            }
            for row in deliveries
        }

    return posts, result.count or 0


async def _cancel_post(post_id: str, owner_id: str, workspace_id: str | None) -> dict:
    """Cancel a pending or scheduled post in Supabase."""
    post = await _get_post(post_id, owner_id, workspace_id)
    if post["status"] not in ("pending", "scheduled"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel post with status '{post['status']}'",
        )

    sb = get_supabase()
    sb.table("posts").update({"status": "cancelled"}).eq("id", post_id).execute()
    sb.table("post_deliveries").update({"status": "cancelled"}).eq("post_id", post_id).execute()
    return await _get_post(post_id, owner_id, workspace_id)


async def _enqueue_post(post_id: str, owner_id: str, status: str) -> None:
    """Enqueue immediate posts for background publishing."""
    if status != "pending":
        return
    publish_post_task.delay(post_id, owner_id)


async def create_internal_post(
    owner_id: str,
    req: CreatePostRequest,
    *,
    workspace_id: str | None = None,
    api_key_id: str | None = None,
    skip_enqueue: bool = False,
) -> dict:
    """Create a post from internal workflows and enqueue it when publish-now."""
    post = await _create_post_record(
        owner_id,
        req,
        workspace_id=workspace_id,
        api_key_id=api_key_id,
    )
    if not skip_enqueue:
        await _enqueue_post(post["id"], owner_id, post["status"])
    return await _get_post(post["id"], owner_id, workspace_id)


def _build_dry_run_preview(
    owner_id: str,
    req: CreatePostRequest,
    *,
    workspace_id: str | None,
) -> DryRunPostResponse:
    social_accounts = _resolve_delivery_accounts(owner_id, req.platforms, workspace_id)
    expected_deliveries = [
        DryRunDeliveryPreview(
            platform=platform,
            social_account_id=social_accounts.get(platform),
        )
        for platform in req.platforms
    ]
    missing_accounts = [
        platform for platform in req.platforms if social_accounts.get(platform) is None
    ]

    return DryRunPostResponse(
        will_enqueue=req.scheduled_for is None,
        media_type=req.media_type,
        scheduled_for=req.scheduled_for,
        platforms=req.platforms,
        missing_accounts=missing_accounts,
        expected_deliveries=expected_deliveries,
        platform_options=req.platform_options,
    )


async def _call_create_internal_post(
    user: CurrentUser,
    req: CreatePostRequest,
    *,
    skip_enqueue: bool,
) -> dict:
    kwargs = {"skip_enqueue": skip_enqueue}
    params = inspect.signature(create_internal_post).parameters
    if "workspace_id" in params:
        kwargs["workspace_id"] = user.workspace_id
    if "api_key_id" in params:
        kwargs["api_key_id"] = user.api_key_id
    return await create_internal_post(user.id, req, **kwargs)


async def _check_bulk_remaining(user: CurrentUser, count: int) -> int:
    params = inspect.signature(check_post_limit_bulk).parameters
    if "workspace_id" in params:
        return await check_post_limit_bulk(
            user.id,
            user.plan,
            count,
            workspace_id=user.workspace_id,
        )
    return await check_post_limit_bulk(user.id, user.plan, count)


def _to_response(post: dict) -> PostResponse:
    """Convert a raw DB row with embedded platform rows to API response."""
    platforms_raw = post.pop("_platforms", {})
    platforms = {
        key: PlatformStatus(
            status=value["status"],
            platform_post_id=value.get("platform_post_id"),
        )
        for key, value in platforms_raw.items()
    }

    media_urls = post.get("media_urls") or []
    if isinstance(media_urls, str):
        media_urls = json.loads(media_urls)

    return PostResponse(
        id=post["id"],
        status=post["status"],
        text=post.get("text"),
        media_urls=media_urls,
        media_type=post.get("media_type", "text"),
        scheduled_for=post.get("scheduled_for"),
        platforms=platforms,
        created_at=post["created_at"],
        updated_at=post["updated_at"],
    )


@router.post(
    "/bulk",
    response_model=BulkPostResponse,
    status_code=201,
    summary="Bulk Create Posts",
    description=(
        "Creates up to 100 posts in a single request. "
        "Platform-specific throttle intervals are applied automatically. "
        "Use `all_or_nothing` mode to reject the entire batch on any failure, "
        "or `partial` to create as many as quota allows."
    ),
)
async def create_posts_bulk(
    req: BulkCreatePostRequest,
    user: CurrentUser,
) -> BulkPostResponse:
    remaining = await _check_bulk_remaining(user, len(req.posts))

    if req.mode == "all_or_nothing" and remaining < len(req.posts):
        raise BillingLimitError(
            f"Insufficient quota for {len(req.posts)} posts "
            f"({remaining} remaining). Upgrade your plan or use partial mode."
        )

    allowed = len(req.posts) if req.mode == "all_or_nothing" else min(len(req.posts), remaining)

    post_dicts = [
        {"platforms": p.platforms, "scheduled_for": p.scheduled_for}
        for p in req.posts
    ]
    offsets = compute_throttle_offsets(post_dicts, datetime.now(UTC))

    results: list[BulkPostItemResult] = []
    to_enqueue: list[tuple[str, str]] = []

    for i, (post_req, offset) in enumerate(zip(req.posts, offsets, strict=True)):
        if i >= allowed:
            results.append(
                BulkPostItemResult(index=i, status="failed", error="Quota exceeded"),
            )
            continue

        actual_req = post_req
        if offset is not None and post_req.scheduled_for is None:
            actual_req = post_req.model_copy(update={"scheduled_for": offset})

        try:
            post = await _call_create_internal_post(user, actual_req, skip_enqueue=True)
            post_response = _to_response(post)
            results.append(
                BulkPostItemResult(index=i, status="created", post=post_response),
            )
            if post["status"] == "pending":
                to_enqueue.append((post["id"], user.id))
        except Exception as exc:
            if req.mode == "all_or_nothing":
                raise
            results.append(
                BulkPostItemResult(index=i, status="failed", error=str(exc)),
            )

    total_created = sum(1 for r in results if r.status == "created")
    total_failed = sum(1 for r in results if r.status == "failed")
    bulk_enqueue(to_enqueue)
    if total_created:
        await invalidate_user_cache(user.id)

    return BulkPostResponse(
        total_submitted=len(req.posts),
        total_created=total_created,
        total_failed=total_failed,
        results=results,
    )


@router.post(
    "",
    response_model=PostResponse | DryRunPostResponse,
    status_code=201,
    summary="Create or Schedule a Post",
    description=(
        "Creates a multi-platform publishing job. "
        "If `scheduled_for` is omitted the post is enqueued immediately; "
        "otherwise it is stored for later dispatch."
    ),
)
async def create_post(
    req: CreatePostRequest,
    user: CurrentUser,
    response: Response,
    dry_run: bool = Query(
        default=False,
        description="Validate and preview delivery wiring without enqueueing or publishing.",
    ),
) -> PostResponse | DryRunPostResponse:
    if dry_run:
        response.status_code = 200
        return _build_dry_run_preview(user.id, req, workspace_id=user.workspace_id)
    post = await _call_create_internal_post(user, req, skip_enqueue=False)
    await invalidate_user_cache(user.id)
    await send_usage_alerts_if_needed(
        user_id=user.id,
        email=user.email,
        plan=user.plan,
        workspace_id=user.workspace_id,
    )
    return _to_response(post)


@router.get(
    "",
    response_model=PostListResponse,
    summary="List Posts",
    description="Returns paginated publishing jobs for the authenticated owner.",
)
async def list_posts(
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> PostListResponse:
    posts, total = await _list_posts(
        user.id,
        user.workspace_id,
        page=page,
        limit=limit,
        status_filter=status,
    )
    return PostListResponse(
        data=[_to_response(post) for post in posts],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Get Post Status",
    description="Returns the current aggregate and per-platform status for a single post job.",
    responses=NOT_FOUND_ERROR,
)
async def get_post(post_id: UUID, user: CurrentUser) -> PostResponse:
    return _to_response(await _get_post(str(post_id), user.id, user.workspace_id))


@router.delete(
    "/{post_id}",
    response_model=PostResponse,
    summary="Cancel a Post",
    description="Cancels a pending or scheduled publishing job before it is delivered.",
    responses={**NOT_FOUND_ERROR, **CONFLICT_ERROR},
)
async def cancel_post(post_id: UUID, user: CurrentUser) -> PostResponse:
    post = await _cancel_post(str(post_id), user.id, user.workspace_id)
    await invalidate_user_cache(user.id)
    return _to_response(post)
