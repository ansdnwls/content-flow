"""Pipeline endpoints — YouTube → Blog auto-publishing."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import AuthenticatedUser, get_current_user
from app.services.youtube_to_blog import (
    PipelineOptions,
    PipelineResult,
    YouTubeToBlogPipeline,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class YouTubeToBlogOptions(BaseModel):
    tags: list[str] = Field(default_factory=list)
    blog_id: str | None = None
    generate_images: bool = True


class YouTubeToBlogRequest(BaseModel):
    youtube_url: str
    options: YouTubeToBlogOptions = Field(default_factory=YouTubeToBlogOptions)


class YouTubeToBlogResponse(BaseModel):
    success: bool
    video_id: str = ""
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    blog_url: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/youtube-to-blog", response_model=YouTubeToBlogResponse)
async def youtube_to_blog(
    body: YouTubeToBlogRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> YouTubeToBlogResponse:
    """Convert a YouTube video into a Naver Blog post.

    Sync endpoint — typically takes 30-60 seconds.
    """
    opts = PipelineOptions(
        blog_id=body.options.blog_id,
        extra_tags=body.options.tags,
        generate_images=body.options.generate_images,
    )

    pipeline = YouTubeToBlogPipeline(options=opts)
    result: PipelineResult = await pipeline.run(body.youtube_url)

    return YouTubeToBlogResponse(
        success=result.success,
        video_id=result.video_id,
        title=result.title,
        tags=result.tags,
        blog_url=result.blog_url,
        error=result.error,
    )
