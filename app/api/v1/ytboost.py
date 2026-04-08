"""YtBoost subscription, shorts, and comment autopilot API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.cache import invalidate_user_cache
from app.core.db import get_supabase
from app.core.errors import NotFoundError
from app.services.shorts_extractor import extract_shorts
from app.services.youtube_comment_autopilot import YouTubeCommentAutopilot
from app.services.youtube_trigger import subscribe_to_channel
from app.services.ytboost_distributor import DistributionResult, YtBoostDistributor

router = APIRouter(prefix="/ytboost", tags=["YtBoost"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class ChannelSubscriptionCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "youtube_channel_id": "UC1234567890",
                "channel_name": "Founder Channel",
                "auto_distribute": True,
                "target_platforms": ["youtube_shorts", "instagram_reels", "tiktok"],
                "auto_comment_mode": "review",
            },
        }
    )

    youtube_channel_id: str
    channel_name: str | None = None
    auto_distribute: bool = False
    target_platforms: list[str] = Field(default_factory=list)
    auto_comment_mode: Literal["auto", "review"] = "review"


class ChannelSubscriptionUpdateRequest(BaseModel):
    channel_name: str | None = None
    auto_distribute: bool | None = None
    target_platforms: list[str] | None = None
    auto_comment_mode: Literal["auto", "review"] | None = None


class ChannelSubscriptionResponse(BaseModel):
    id: str
    user_id: str
    youtube_channel_id: str
    channel_name: str | None = None
    subscribed_at: datetime
    last_checked_at: datetime | None = None
    auto_distribute: bool = False
    target_platforms: list[str] = Field(default_factory=list)
    auto_comment_mode: str = "review"
    created_at: datetime
    updated_at: datetime


class DistributionResponse(BaseModel):
    requested_platform: str
    adapter_platform: str
    status: str
    post_id: str | None = None


class ShortResponse(BaseModel):
    id: str
    user_id: str
    source_video_id: str
    source_channel_id: str
    start_seconds: int
    end_seconds: int
    hook_line: str | None = None
    suggested_title: str | None = None
    suggested_hashtags: list[str] = Field(default_factory=list)
    reason: str | None = None
    clip_file_url: str | None = None
    status: str
    created_at: datetime
    approved_at: datetime | None = None
    updated_at: datetime


class ShortsListResponse(BaseModel):
    data: list[ShortResponse]
    total: int


class ApproveShortRequest(BaseModel):
    target_platforms: list[str] | None = None


class ApproveShortResponse(BaseModel):
    short: ShortResponse
    distributions: list[DistributionResponse] = Field(default_factory=list)


class ExtractShortsRequest(BaseModel):
    video_id: str
    source_channel_id: str
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    video_metadata: dict[str, Any] = Field(default_factory=dict)


class PendingCommentResponse(BaseModel):
    id: str
    user_id: str
    platform: str
    platform_post_id: str
    platform_comment_id: str
    author_name: str
    text: str
    ai_reply: str | None = None
    reply_status: str
    created_at: datetime
    updated_at: datetime


class PendingCommentListResponse(BaseModel):
    data: list[PendingCommentResponse]
    total: int


class CommentApproveRequest(BaseModel):
    text: str | None = None


class CommentApproveResponse(BaseModel):
    success: bool
    platform_reply_id: str | None = None
    error: str | None = None
    ai_reply: str | None = None


def _channel_response(row: dict[str, Any]) -> ChannelSubscriptionResponse:
    return ChannelSubscriptionResponse(
        id=row["id"],
        user_id=row["user_id"],
        youtube_channel_id=row["youtube_channel_id"],
        channel_name=row.get("channel_name"),
        subscribed_at=row["subscribed_at"],
        last_checked_at=row.get("last_checked_at"),
        auto_distribute=row.get("auto_distribute", False),
        target_platforms=list(row.get("target_platforms") or []),
        auto_comment_mode=row.get("auto_comment_mode", "review"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _short_response(row: dict[str, Any]) -> ShortResponse:
    return ShortResponse(
        id=row["id"],
        user_id=row["user_id"],
        source_video_id=row["source_video_id"],
        source_channel_id=row["source_channel_id"],
        start_seconds=row["start_seconds"],
        end_seconds=row["end_seconds"],
        hook_line=row.get("hook_line"),
        suggested_title=row.get("suggested_title"),
        suggested_hashtags=list(row.get("suggested_hashtags") or []),
        reason=row.get("reason"),
        clip_file_url=row.get("clip_file_url"),
        status=row["status"],
        created_at=row["created_at"],
        approved_at=row.get("approved_at"),
        updated_at=row["updated_at"],
    )


def _distribution_response(result: DistributionResult) -> DistributionResponse:
    return DistributionResponse(
        requested_platform=result.requested_platform,
        adapter_platform=result.adapter_platform,
        status=result.status,
        post_id=result.post_id,
    )


def _load_owned_channel(channel_id: str, user_id: str) -> dict[str, Any]:
    row = (
        get_supabase()
        .table("ytboost_subscriptions")
        .select("*")
        .eq("id", channel_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise NotFoundError("YtBoost channel", channel_id)
    return row


def _load_owned_short(short_id: str, user_id: str) -> dict[str, Any]:
    row = (
        get_supabase()
        .table("ytboost_shorts")
        .select("*")
        .eq("id", short_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise NotFoundError("YtBoost short", short_id)
    return row


@router.post(
    "/channels",
    response_model=ChannelSubscriptionResponse,
    status_code=201,
    summary="Subscribe YouTube Channel",
)
async def create_channel_subscription(
    req: ChannelSubscriptionCreateRequest,
    user: CurrentUser,
) -> ChannelSubscriptionResponse:
    subscribe_result = await subscribe_to_channel(req.youtube_channel_id, user.id)
    if subscribe_result.get("status_code", 500) >= 400:
        raise HTTPException(status_code=502, detail="YouTube subscription request failed")

    result = (
        get_supabase()
        .table("ytboost_subscriptions")
        .upsert(
            {
                "user_id": user.id,
                "youtube_channel_id": req.youtube_channel_id,
                "channel_name": req.channel_name,
                "auto_distribute": req.auto_distribute,
                "target_platforms": req.target_platforms,
                "auto_comment_mode": req.auto_comment_mode,
                "subscribed_at": datetime.now(UTC).isoformat(),
            },
            on_conflict="user_id,youtube_channel_id",
        )
        .execute()
    )
    await invalidate_user_cache(user.id)
    return _channel_response(result.data[0])


@router.get(
    "/channels",
    response_model=list[ChannelSubscriptionResponse],
    summary="List Subscribed YouTube Channels",
)
async def list_channel_subscriptions(user: CurrentUser) -> list[ChannelSubscriptionResponse]:
    result = (
        get_supabase()
        .table("ytboost_subscriptions")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_channel_response(row) for row in result.data]


@router.patch(
    "/channels/{channel_id}",
    response_model=ChannelSubscriptionResponse,
    summary="Update Channel Subscription",
    responses=NOT_FOUND_ERROR,
)
async def update_channel_subscription(
    channel_id: str,
    req: ChannelSubscriptionUpdateRequest,
    user: CurrentUser,
) -> ChannelSubscriptionResponse:
    _load_owned_channel(channel_id, user.id)
    updates = req.model_dump(exclude_none=True)
    if not updates:
        return _channel_response(_load_owned_channel(channel_id, user.id))

    updated = (
        get_supabase()
        .table("ytboost_subscriptions")
        .update(updates)
        .eq("id", channel_id)
        .eq("user_id", user.id)
        .execute()
    )
    await invalidate_user_cache(user.id)
    return _channel_response(updated.data[0])


@router.delete(
    "/channels/{channel_id}",
    status_code=200,
    summary="Delete Channel Subscription",
    responses=NOT_FOUND_ERROR,
)
async def delete_channel_subscription(channel_id: str, user: CurrentUser) -> dict[str, str]:
    _load_owned_channel(channel_id, user.id)
    get_supabase().table("ytboost_subscriptions").delete().eq("id", channel_id).eq(
        "user_id", user.id
    ).execute()
    await invalidate_user_cache(user.id)
    return {"status": "deleted"}


@router.get(
    "/shorts",
    response_model=ShortsListResponse,
    summary="List Extracted Shorts",
)
async def list_shorts(
    user: CurrentUser,
    status: str | None = None,
) -> ShortsListResponse:
    query = get_supabase().table("ytboost_shorts").select("*", count="exact").eq("user_id", user.id)
    if status:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).execute()
    return ShortsListResponse(
        data=[_short_response(row) for row in result.data],
        total=result.count or 0,
    )


@router.get(
    "/shorts/{short_id}",
    response_model=ShortResponse,
    summary="Get Extracted Short",
    responses=NOT_FOUND_ERROR,
)
async def get_short(short_id: str, user: CurrentUser) -> ShortResponse:
    return _short_response(_load_owned_short(short_id, user.id))


@router.post(
    "/shorts/extract",
    response_model=ShortsListResponse,
    status_code=201,
    summary="Extract Shorts from a Video",
)
async def extract_video_shorts(
    req: ExtractShortsRequest,
    user: CurrentUser,
) -> ShortsListResponse:
    rows = await extract_shorts(
        req.video_id,
        user.id,
        req.source_channel_id,
        transcript=req.transcript,
        video_metadata=req.video_metadata,
    )
    await invalidate_user_cache(user.id)
    return ShortsListResponse(
        data=[_short_response(row) for row in rows],
        total=len(rows),
    )


@router.post(
    "/shorts/{short_id}/approve",
    response_model=ApproveShortResponse,
    summary="Approve and Optionally Distribute a Short",
    responses=NOT_FOUND_ERROR,
)
async def approve_short(
    short_id: str,
    req: ApproveShortRequest,
    user: CurrentUser,
) -> ApproveShortResponse:
    short_row = _load_owned_short(short_id, user.id)
    if short_row["status"] == "rejected":
        raise HTTPException(status_code=409, detail="Rejected shorts cannot be approved")

    subscription = (
        get_supabase()
        .table("ytboost_subscriptions")
        .select("*")
        .eq("user_id", user.id)
        .eq("youtube_channel_id", short_row["source_channel_id"])
        .maybe_single()
        .execute()
        .data
    )
    target_platforms = req.target_platforms
    if target_platforms is None and subscription:
        target_platforms = list(subscription.get("target_platforms") or [])
    if target_platforms is None:
        target_platforms = []

    distributions: list[DistributionResult] = []
    new_status = "approved"
    if target_platforms:
        distributions = await YtBoostDistributor().distribute_short(
            short_row,
            target_platforms,
            user.id,
        )
        if any(result.status == "queued" for result in distributions):
            new_status = "distributed"

    updated = (
        get_supabase()
        .table("ytboost_shorts")
        .update(
            {
                "status": new_status,
                "approved_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", short_id)
        .eq("user_id", user.id)
        .execute()
    )
    await invalidate_user_cache(user.id)
    return ApproveShortResponse(
        short=_short_response(updated.data[0]),
        distributions=[_distribution_response(item) for item in distributions],
    )


@router.post(
    "/shorts/{short_id}/reject",
    response_model=ShortResponse,
    summary="Reject a Short",
    responses=NOT_FOUND_ERROR,
)
async def reject_short(short_id: str, user: CurrentUser) -> ShortResponse:
    _load_owned_short(short_id, user.id)
    updated = (
        get_supabase()
        .table("ytboost_shorts")
        .update({"status": "rejected"})
        .eq("id", short_id)
        .eq("user_id", user.id)
        .execute()
    )
    await invalidate_user_cache(user.id)
    return _short_response(updated.data[0])


@router.get(
    "/comments/pending",
    response_model=PendingCommentListResponse,
    summary="List Pending YouTube Comment Replies",
)
async def list_pending_comment_replies(user: CurrentUser) -> PendingCommentListResponse:
    result = (
        get_supabase()
        .table("comments")
        .select("*", count="exact")
        .eq("user_id", user.id)
        .eq("platform", "youtube")
        .eq("reply_status", "review_pending")
        .order("created_at", desc=True)
        .execute()
    )
    return PendingCommentListResponse(
        data=[PendingCommentResponse(**row) for row in result.data],
        total=result.count or 0,
    )


@router.post(
    "/comments/{comment_id}/approve",
    response_model=CommentApproveResponse,
    summary="Approve a Prepared YouTube Reply",
)
async def approve_comment_reply(
    comment_id: str,
    req: CommentApproveRequest,
    user: CurrentUser,
) -> CommentApproveResponse:
    result = await YouTubeCommentAutopilot().approve_reply(
        comment_id,
        user.id,
        text=req.text,
    )
    if not result.get("success") and result.get("error") == "Comment not found":
        raise NotFoundError("Comment", comment_id)
    await invalidate_user_cache(user.id)
    return CommentApproveResponse(**result)


@router.post(
    "/comments/{comment_id}/edit",
    response_model=CommentApproveResponse,
    summary="Edit and Send a Prepared YouTube Reply",
)
async def edit_comment_reply(
    comment_id: str,
    req: CommentApproveRequest,
    user: CurrentUser,
) -> CommentApproveResponse:
    if not req.text:
        raise HTTPException(status_code=400, detail="Edited reply text is required")
    result = await YouTubeCommentAutopilot().approve_reply(
        comment_id,
        user.id,
        text=req.text,
    )
    if not result.get("success") and result.get("error") == "Comment not found":
        raise NotFoundError("Comment", comment_id)
    await invalidate_user_cache(user.id)
    return CommentApproveResponse(**result)
