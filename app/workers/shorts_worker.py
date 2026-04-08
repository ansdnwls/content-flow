"""Celery worker for YtBoost shorts extraction."""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.shorts_extractor import extract_shorts
from app.workers.celery_app import celery_app


async def run_shorts_extraction(
    *,
    video_id: str,
    user_id: str,
    source_channel_id: str,
    transcript: list[dict[str, Any]] | None = None,
    video_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shorts = await extract_shorts(
        video_id,
        user_id,
        source_channel_id,
        transcript=transcript,
        video_metadata=video_metadata,
    )
    return {
        "video_id": video_id,
        "user_id": user_id,
        "source_channel_id": source_channel_id,
        "count": len(shorts),
        "shorts": shorts,
    }


@celery_app.task(name="contentflow.extract_ytboost_shorts")
def extract_ytboost_shorts_task(
    video_id: str,
    user_id: str,
    source_channel_id: str,
    transcript: list[dict[str, Any]] | None = None,
    video_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        run_shorts_extraction(
            video_id=video_id,
            user_id=user_id,
            source_channel_id=source_channel_id,
            transcript=transcript,
            video_metadata=video_metadata,
        )
    )
