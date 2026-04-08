"""Content Bomb API for generating platform variants from a single topic."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, CONFLICT_ERROR, NOT_FOUND_ERROR
from app.core.db import get_supabase
from app.core.errors import NotFoundError
from app.workers.bomb_worker import publish_bomb_task, transform_bomb_task

router = APIRouter(prefix="/bombs", tags=["Bombs"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class CreateBombRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "DUI 3-strike laws and what drivers misunderstand most"
            },
        },
    )

    topic: str = Field(
        description="Single source topic used to create all platform variants.",
    )


class BombResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "bomb_123",
                "topic": "DUI 3-strike laws and what drivers misunderstand most",
                "status": "ready",
                "platform_contents": {"youtube": {"title": "DUI 3-strike laws | Full breakdown"}},
                "created_at": "2026-04-07T00:00:00+00:00",
                "updated_at": "2026-04-07T00:00:05+00:00",
            },
        },
    )

    id: str
    topic: str
    status: str
    platform_contents: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str


async def _create_bomb(user: AuthenticatedUser, topic: str) -> dict:
    sb = get_supabase()
    result = (
        sb.table("bombs")
        .insert(
            {
                "user_id": user.id,
                "topic": topic,
                "status": "queued",
                "platform_contents": {},
            },
        )
        .execute()
    )
    return result.data[0]


async def _get_bomb(bomb_id: str, user_id: str) -> dict:
    sb = get_supabase()
    result = (
        sb.table("bombs")
        .select("*")
        .eq("id", bomb_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise NotFoundError("Bomb", bomb_id)
    return result.data


async def _enqueue_bomb_transform(bomb_id: str, user_id: str) -> None:
    transform_bomb_task.delay(bomb_id, user_id)


async def _enqueue_bomb_publish(bomb_id: str, user_id: str) -> None:
    publish_bomb_task.delay(bomb_id, user_id)


@router.post(
    "",
    response_model=BombResponse,
    status_code=201,
    summary="Create Content Bomb",
    description=(
        "Creates a content bomb that expands a single topic into "
        "platform-specific variants."
    ),
)
async def create_bomb(req: CreateBombRequest, user: CurrentUser) -> BombResponse:
    bomb = await _create_bomb(user, req.topic)
    await _enqueue_bomb_transform(bomb["id"], user.id)
    return BombResponse(**bomb)


@router.get(
    "/{bomb_id}",
    response_model=BombResponse,
    summary="Get Content Bomb",
    description=(
        "Returns the transformation status and per-platform generated "
        "content for a bomb."
    ),
    responses=NOT_FOUND_ERROR,
)
async def get_bomb(bomb_id: UUID, user: CurrentUser) -> BombResponse:
    return BombResponse(**(await _get_bomb(str(bomb_id), user.id)))


@router.post(
    "/{bomb_id}/publish",
    response_model=BombResponse,
    summary="Publish Content Bomb",
    description="Queues the generated platform variants for asynchronous publication.",
    responses={**NOT_FOUND_ERROR, **CONFLICT_ERROR},
)
async def publish_bomb(bomb_id: UUID, user: CurrentUser) -> BombResponse:
    bomb = await _get_bomb(str(bomb_id), user.id)
    if bomb["status"] not in {"ready", "published"}:
        raise HTTPException(status_code=409, detail="Bomb must be ready before publish")
    await _enqueue_bomb_publish(str(bomb_id), user.id)
    return BombResponse(**bomb)
