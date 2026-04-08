"""Comment Autopilot API — collect comments and generate AI replies."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, CONFLICT_ERROR, NOT_FOUND_ERROR
from app.core.errors import NotFoundError
from app.services.comment_service import CommentService

router = APIRouter(prefix="/comments", tags=["Comments"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class CollectRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "platform": "youtube",
                "platform_post_id": "abc123",
                "credentials": {"access_token": "ya29..."},
            },
        },
    )

    platform: str = Field(description="Platform name (youtube, tiktok, instagram)")
    platform_post_id: str = Field(description="Post ID on the platform")
    credentials: dict[str, str] = Field(description="Platform API credentials")


class ReplyRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "credentials": {"access_token": "ya29..."},
                "context": "Video about Python tips",
            },
        },
    )

    credentials: dict[str, str] = Field(description="Platform API credentials")
    context: str = Field(default="", description="Post context for better replies")


class CommentResponse(BaseModel):
    id: str
    user_id: str
    platform: str
    platform_post_id: str
    platform_comment_id: str
    author_name: str
    text: str
    ai_reply: str | None = None
    reply_status: str = "pending"
    created_at: str
    updated_at: str


class CommentListResponse(BaseModel):
    data: list[CommentResponse]
    total: int
    page: int
    limit: int


class ReplyResponse(BaseModel):
    success: bool
    ai_reply: str | None = None
    platform_reply_id: str | None = None
    error: str | None = None


@router.post(
    "/collect",
    response_model=list[CommentResponse],
    summary="Collect Comments",
    description="Fetch and store comments from a platform post.",
)
async def collect_comments(req: CollectRequest, user: CurrentUser) -> list[CommentResponse]:
    service = CommentService()
    stored = await service.collect_comments(
        user_id=user.id,
        platform=req.platform,
        platform_post_id=req.platform_post_id,
        credentials=req.credentials,
    )
    return [CommentResponse(**row) for row in stored]


@router.get(
    "",
    response_model=CommentListResponse,
    summary="List Comments",
    description="List collected comments with optional filters.",
)
async def list_comments(
    user: CurrentUser,
    platform: str | None = None,
    platform_post_id: str | None = None,
    reply_status: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> CommentListResponse:
    service = CommentService()
    data, total = await service.list_comments(
        user_id=user.id,
        platform=platform,
        platform_post_id=platform_post_id,
        reply_status=reply_status,
        page=page,
        limit=limit,
    )
    return CommentListResponse(
        data=[CommentResponse(**row) for row in data],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Get Comment",
    description="Retrieve a single comment by ID.",
    responses=NOT_FOUND_ERROR,
)
async def get_comment(comment_id: UUID, user: CurrentUser) -> CommentResponse:
    service = CommentService()
    comment = await service.get_comment(str(comment_id), user.id)
    if not comment:
        raise NotFoundError("Comment", str(comment_id))
    return CommentResponse(**comment)


@router.post(
    "/{comment_id}/reply",
    response_model=ReplyResponse,
    summary="AI Reply to Comment",
    description="Generate an AI reply and post it to the platform.",
    responses={**NOT_FOUND_ERROR, **CONFLICT_ERROR},
)
async def reply_to_comment(
    comment_id: UUID,
    req: ReplyRequest,
    user: CurrentUser,
) -> ReplyResponse:
    service = CommentService()
    comment = await service.get_comment(str(comment_id), user.id)
    if not comment:
        raise NotFoundError("Comment", str(comment_id))
    if comment.get("reply_status") == "replied":
        raise HTTPException(status_code=409, detail="Already replied to this comment")

    result = await service.auto_reply(
        comment_id=str(comment_id),
        user_id=user.id,
        credentials=req.credentials,
        context=req.context,
    )
    return ReplyResponse(**result)
