"""Card news generation API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/card-news", tags=["card-news"])

# In-memory job store (replace with Supabase in production)
_jobs: dict[str, dict[str, Any]] = {}


class CardNewsRequest(BaseModel):
    source_type: str = Field(
        ...,
        description="youtube|news|rss|github|url|text",
    )
    source: str = Field(
        ...,
        description="URL, keyword, repo name, or raw text",
    )
    title: str | None = Field(
        default=None,
        description="Override title (for text source)",
    )
    channel_name: str | None = Field(
        default=None,
        description="Override channel name on cards",
    )
    schedule_at: datetime | None = Field(
        default=None,
        description="Schedule generation (ISO 8601). None = immediate.",
    )


class CardNewsResponse(BaseModel):
    job_id: str
    status: str  # processing | scheduled | done | failed
    card_paths: list[str] = []
    card_count: int = 0
    color_theme: str = ""
    error: str = ""
    scheduled_at: str | None = None


@router.post("/generate", response_model=CardNewsResponse)
async def generate_card_news(req: CardNewsRequest) -> CardNewsResponse:
    """Generate card news from any supported source."""
    from app.services.content_fetcher import ContentFetcher, _VALID_SOURCE_TYPES
    from app.services.card_news_generator import CardNewsGenerator

    if req.source_type not in _VALID_SOURCE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source_type. Valid: {', '.join(sorted(_VALID_SOURCE_TYPES))}",
        )

    job_id = str(uuid.uuid4())

    # Scheduled generation
    if req.schedule_at:
        _jobs[job_id] = {
            "status": "scheduled",
            "request": req.model_dump(),
            "scheduled_at": req.schedule_at.isoformat(),
        }
        return CardNewsResponse(
            job_id=job_id,
            status="scheduled",
            scheduled_at=req.schedule_at.isoformat(),
        )

    # Immediate generation
    _jobs[job_id] = {"status": "processing"}

    try:
        # 1. Fetch content
        fetcher = ContentFetcher()
        kwargs: dict[str, Any] = {}
        if req.source_type == "text" and req.title:
            kwargs["title"] = req.title
        content = await fetcher.fetch(req.source_type, req.source, **kwargs)

        # 2. Generate card news
        gen = CardNewsGenerator()
        result = await gen.generate_from_text(
            title=content.title,
            text=content.text,
            source_id=content.source_id,
        )

        if not result.success:
            _jobs[job_id] = {"status": "failed", "error": result.error}
            return CardNewsResponse(
                job_id=job_id,
                status="failed",
                error=result.error,
            )

        _jobs[job_id] = {
            "status": "done",
            "card_paths": result.image_paths,
            "card_count": result.card_count,
            "color_theme": result.color_theme,
        }
        return CardNewsResponse(
            job_id=job_id,
            status="done",
            card_paths=result.image_paths,
            card_count=result.card_count,
            color_theme=result.color_theme,
        )

    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        logger.error("card_news_api_failed", error=err)
        _jobs[job_id] = {"status": "failed", "error": err}
        return CardNewsResponse(
            job_id=job_id,
            status="failed",
            error=err,
        )


@router.get("/{job_id}", response_model=CardNewsResponse)
async def get_card_news_status(job_id: str) -> CardNewsResponse:
    """Check card news generation status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return CardNewsResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        card_paths=job.get("card_paths", []),
        card_count=job.get("card_count", 0),
        color_theme=job.get("color_theme", ""),
        error=job.get("error", ""),
        scheduled_at=job.get("scheduled_at"),
    )
