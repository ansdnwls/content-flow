"""Integration helpers for yt-factory -> YtBoost handoff."""

from __future__ import annotations

from typing import Any

from app.services.youtube_trigger import (
    YouTubeVideoNotification,
    is_known_video,
    mark_video_detected,
)
from app.workers.shorts_worker import extract_ytboost_shorts_task


class YtFactoryIntegration:
    """Bridge yt-factory publish completion events into YtBoost extraction."""

    async def handle_publish_complete(
        self,
        *,
        user_id: str,
        youtube_video_id: str,
        youtube_channel_id: str,
        transcript: list[dict[str, Any]] | None = None,
        video_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if is_known_video(user_id, youtube_video_id):
            return {
                "queued": False,
                "duplicate": True,
                "video_id": youtube_video_id,
                "channel_id": youtube_channel_id,
            }

        await mark_video_detected(
            user_id,
            YouTubeVideoNotification(
                video_id=youtube_video_id,
                channel_id=youtube_channel_id,
                title=(video_metadata or {}).get("title"),
            ),
        )
        extract_ytboost_shorts_task.delay(
            youtube_video_id,
            user_id,
            youtube_channel_id,
            transcript,
            video_metadata,
        )
        return {
            "queued": True,
            "duplicate": False,
            "video_id": youtube_video_id,
            "channel_id": youtube_channel_id,
        }
