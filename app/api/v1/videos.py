"""Videos API for queued AI generation jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.api.error_responses import COMMON_RESPONSES, NOT_FOUND_ERROR
from app.core.cache import cache, invalidate_user_cache
from app.core.db import get_supabase
from app.core.errors import NotFoundError
from app.services.usage_alerts import send_usage_alerts_if_needed
from app.services.video_templates import (
    BUILTIN_TEMPLATES,
    db_row_to_template,
    get_template,
    list_builtin_templates,
)
from app.workers.video_worker import generate_video_task

router = APIRouter(prefix="/videos", tags=["Videos"], responses=COMMON_RESPONSES)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


class AutoPublishRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "platforms": ["youtube", "tiktok"],
                "scheduled_for": "2026-04-07T09:00:00+09:00",
            },
        },
    )

    enabled: bool = False
    platforms: list[str] = Field(default_factory=list)
    scheduled_for: datetime | None = None


class CreateVideoRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "DUI 3-strike laws",
                "mode": "legal",
                "language": "ko",
                "format": "shorts",
                "style": "realistic",
                "auto_publish": {
                    "enabled": True,
                    "platforms": ["youtube"],
                    "scheduled_for": "2026-04-07T09:00:00+09:00",
                },
            },
        },
    )

    topic: str = Field(..., max_length=500)
    mode: str = Field(..., max_length=50)
    language: str = Field(default="en", max_length=10)
    format: str = Field(default="shorts", max_length=50)
    style: str | None = Field(default=None, max_length=50)
    template: str | None = Field(
        default=None,
        description="Built-in or custom template ID (e.g. news_brief, listicle).",
    )
    auto_publish: AutoPublishRequest = Field(default_factory=AutoPublishRequest)


class VideoResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "vid_123",
                "status": "queued",
                "topic": "DUI 3-strike laws",
                "mode": "legal",
                "language": "ko",
                "format": "shorts",
                "style": "realistic",
                "output_url": None,
                "auto_publish": {"enabled": True, "platforms": ["youtube"]},
                "created_at": "2026-04-06T21:20:00+00:00",
                "updated_at": "2026-04-06T21:20:00+00:00",
            },
        },
    )

    id: str
    status: str
    topic: str
    mode: str
    language: str
    format: str
    style: str | None = None
    template: str | None = None
    output_url: str | None = None
    auto_publish: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


async def _create_video_job(user: AuthenticatedUser, req: CreateVideoRequest) -> dict:
    """Insert a queued video generation job into Supabase."""
    sb = get_supabase()
    result = (
        sb.table("video_jobs")
        .insert(
            {
                "owner_id": user.id,
                "workspace_id": user.workspace_id,
                "topic": req.topic,
                "mode": req.mode,
                "language": req.language,
                "format": req.format,
                "style": req.style,
                "template": req.template,
                "status": "queued",
                "auto_publish": req.auto_publish.model_dump(mode="json"),
            },
        )
        .execute()
    )
    return result.data[0]


async def _get_video(video_id: str, owner_id: str, workspace_id: str | None) -> dict:
    """Fetch a single video job from Supabase."""
    sb = get_supabase()
    query = sb.table("video_jobs").select("*").eq("id", video_id).eq("owner_id", owner_id)
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    result = query.maybe_single().execute()
    if not result.data:
        raise NotFoundError("Video job", video_id)
    return result.data


async def _enqueue_video_generation(video_id: str, owner_id: str) -> None:
    """Queue the background worker that calls yt-factory."""
    generate_video_task.delay(video_id, owner_id)


def _to_response(video: dict) -> VideoResponse:
    auto_publish = video.get("auto_publish") or {}
    if not isinstance(auto_publish, dict):
        auto_publish = {}

    return VideoResponse(
        id=video["id"],
        status=video["status"],
        topic=video["topic"],
        mode=video["mode"],
        language=video["language"],
        format=video["format"],
        style=video.get("style"),
        template=video.get("template"),
        output_url=video.get("output_url"),
        auto_publish=auto_publish,
        created_at=video["created_at"],
        updated_at=video["updated_at"],
    )


@router.post(
    "/generate",
    response_model=VideoResponse,
    status_code=201,
    summary="Generate a Video",
    description=(
        "Creates an AI video generation job and enqueues it for background processing "
        "through the yt-factory generation engine."
    ),
)
async def create_video(req: CreateVideoRequest, user: CurrentUser) -> VideoResponse:
    video = await _create_video_job(user, req)
    await _enqueue_video_generation(video["id"], user.id)
    await invalidate_user_cache(user.id)
    await send_usage_alerts_if_needed(
        user_id=user.id,
        email=user.email,
        plan=user.plan,
        workspace_id=user.workspace_id,
    )
    return _to_response(await _get_video(video["id"], user.id, user.workspace_id))


# ---------------------------------------------------------------------------
# Template models
# ---------------------------------------------------------------------------

class SceneResponse(BaseModel):
    name: str
    duration_seconds: int
    description: str
    caption_style: str = "bottom_center"


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    duration_seconds: int
    scenes: list[SceneResponse]
    caption_style: str
    voice_tone: str
    bgm_mood: str
    is_builtin: bool = True
    owner_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateTemplateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "My Custom Template",
                "description": "A branded intro + 3 segments + CTA.",
                "duration_seconds": 45,
                "scenes": [
                    {"name": "intro", "duration_seconds": 8, "description": "Brand intro."},
                    {"name": "body", "duration_seconds": 30, "description": "Main content."},
                    {"name": "cta", "duration_seconds": 7, "description": "Call to action."},
                ],
                "caption_style": "bold_white",
                "voice_tone": "friendly",
                "bgm_mood": "upbeat",
            },
        },
    )

    name: str
    description: str = ""
    duration_seconds: int = Field(gt=0, le=600)
    scenes: list[SceneResponse] = Field(min_length=1)
    caption_style: str = "bold_white"
    voice_tone: str = "neutral"
    bgm_mood: str = "ambient"


class TemplateListResponse(BaseModel):
    data: list[TemplateResponse]
    total: int


def _custom_row_to_response(row: dict) -> TemplateResponse:
    """Convert a DB row to TemplateResponse, excluding is_builtin from to_dict."""
    tmpl = db_row_to_template(row)
    d = tmpl.to_dict()
    d.pop("is_builtin", None)
    return TemplateResponse(
        **d,
        is_builtin=False,
        owner_id=row.get("owner_id"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


# ---------------------------------------------------------------------------
# Template endpoints (MUST be before /{video_id} to avoid route conflicts)
# ---------------------------------------------------------------------------

@router.get(
    "/templates",
    response_model=TemplateListResponse,
    summary="List Video Templates",
    description="Returns all available video templates (built-in + user custom).",
)
@cache(ttl=3600, key_prefix="video-templates")
async def list_templates(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> TemplateListResponse:
    builtin = list_builtin_templates()
    builtin_responses = [TemplateResponse(**t) for t in builtin]

    sb = get_supabase()
    result = sb.table("video_templates").select("*").eq("owner_id", user.id).execute()
    custom = [_custom_row_to_response(row) for row in result.data]

    all_templates = builtin_responses + custom
    return TemplateListResponse(data=all_templates, total=len(all_templates))


@router.get(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    summary="Get Video Template",
    description="Returns a single video template by ID (built-in or custom).",
    responses=NOT_FOUND_ERROR,
)
async def get_template_detail(template_id: str, user: CurrentUser) -> TemplateResponse:
    builtin = get_template(template_id)
    if builtin:
        return TemplateResponse(**builtin.to_dict())

    sb = get_supabase()
    result = (
        sb.table("video_templates")
        .select("*")
        .eq("id", template_id)
        .eq("owner_id", user.id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise NotFoundError("Video template", template_id)

    return _custom_row_to_response(result.data)


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=201,
    summary="Create Custom Template",
    description="Creates a user-owned custom video template.",
)
async def create_template(
    req: CreateTemplateRequest, user: CurrentUser,
) -> TemplateResponse:
    if req.name.lower().replace(" ", "_") in BUILTIN_TEMPLATES:
        raise HTTPException(
            status_code=409,
            detail=f"Template name conflicts with built-in template '{req.name}'",
        )

    sb = get_supabase()
    result = (
        sb.table("video_templates")
        .insert({
            "owner_id": user.id,
            "name": req.name,
            "description": req.description,
            "duration_seconds": req.duration_seconds,
            "scenes": [s.model_dump() for s in req.scenes],
            "caption_style": req.caption_style,
            "voice_tone": req.voice_tone,
            "bgm_mood": req.bgm_mood,
        })
        .execute()
    )
    await invalidate_user_cache(user.id)
    return _custom_row_to_response(result.data[0])


# ---------------------------------------------------------------------------
# Video detail (after /templates to avoid route conflict)
# ---------------------------------------------------------------------------

@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get Video Job Status",
    description="Returns the current state and output URL for a video generation job.",
    responses=NOT_FOUND_ERROR,
)
async def get_video(video_id: UUID, user: CurrentUser) -> VideoResponse:
    return _to_response(await _get_video(str(video_id), user.id, user.workspace_id))
