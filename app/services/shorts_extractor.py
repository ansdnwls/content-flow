"""Automatic short clip extraction for YtBoost."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.core.db import get_supabase


@dataclass(frozen=True)
class ShortClip:
    start_seconds: int
    end_seconds: int
    hook_line: str
    reason: str
    suggested_title: str
    suggested_hashtags: list[str]
    clip_file_url: str | None = None

    def to_row(
        self,
        *,
        user_id: str,
        source_video_id: str,
        source_channel_id: str,
    ) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "source_video_id": source_video_id,
            "source_channel_id": source_channel_id,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "hook_line": self.hook_line,
            "reason": self.reason,
            "suggested_title": self.suggested_title,
            "suggested_hashtags": self.suggested_hashtags,
            "clip_file_url": self.clip_file_url,
            "status": "pending",
        }


def _duration_to_seconds(duration: str | int | None) -> int:
    if isinstance(duration, int):
        return duration
    if not duration:
        return 600
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 600
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _fallback_segments(duration_seconds: int) -> list[ShortClip]:
    duration = max(duration_seconds, 180)
    anchors = [0, duration // 3, max(0, (duration * 2) // 3 - 15)]
    clips: list[ShortClip] = []
    for index, start in enumerate(anchors, start=1):
        end = min(duration, start + 55)
        clips.append(
            ShortClip(
                start_seconds=int(start),
                end_seconds=int(end),
                hook_line=f"Clip {index} hook",
                reason="Fallback selection based on evenly spaced highlights.",
                suggested_title=f"Short highlight {index}",
                suggested_hashtags=["#shorts", "#ytboost", f"#clip{index}"],
                clip_file_url=(
                    f"https://cdn.contentflow.dev/ytboost/"
                    f"fallback_{index}_{int(start)}_{int(end)}.mp4"
                ),
            ),
        )
    return clips


async def _select_segments_with_claude(
    transcript: list[dict[str, Any]],
    *,
    duration_seconds: int,
) -> list[ShortClip]:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _fallback_segments(duration_seconds)

    prompt = (
        "Find the best 3 short-form clip segments from this YouTube transcript. "
        "Return strict JSON as a list of objects with: start_seconds, end_seconds, "
        "hook_line, reason, suggested_title, suggested_hashtags. "
        "Each clip must be 45-60 seconds and self-contained.\n\n"
        f"Transcript:\n{json.dumps(transcript, ensure_ascii=True)}"
    )

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{settings.anthropic_api_base_url.rstrip('/')}/messages",
            headers={
                "x-api-key": settings.anthropic_api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        payload = response.json()

    text = "".join(
        part.get("text", "")
        for part in payload.get("content", [])
        if part.get("type") == "text"
    ).strip()
    try:
        raw_segments = json.loads(text)
    except json.JSONDecodeError:
        return _fallback_segments(duration_seconds)

    clips: list[ShortClip] = []
    for index, segment in enumerate(raw_segments[:3], start=1):
        start = int(segment.get("start_seconds", max((index - 1) * 60, 0)))
        end = int(segment.get("end_seconds", start + 55))
        clips.append(
            ShortClip(
                start_seconds=start,
                end_seconds=end,
                hook_line=segment.get("hook_line", f"Hook {index}"),
                reason=segment.get("reason", "Selected by Claude for high retention potential."),
                suggested_title=segment.get("suggested_title", f"Short highlight {index}"),
                suggested_hashtags=list(segment.get("suggested_hashtags", ["#shorts", "#ytboost"])),
                clip_file_url=(
                    f"https://cdn.contentflow.dev/ytboost/"
                    f"claude_{index}_{start}_{end}.mp4"
                ),
            ),
        )
    return clips or _fallback_segments(duration_seconds)


async def extract_shorts(
    video_id: str,
    user_id: str,
    source_channel_id: str,
    *,
    transcript: list[dict[str, Any]] | None = None,
    video_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Select up to 3 short clips and persist them as pending approval items."""
    transcript = transcript or []
    metadata = video_metadata or {}
    duration_seconds = _duration_to_seconds(
        metadata.get("duration_seconds") or metadata.get("duration"),
    )

    if transcript:
        clips = await _select_segments_with_claude(
            transcript,
            duration_seconds=duration_seconds,
        )
    else:
        clips = _fallback_segments(duration_seconds)

    sb = get_supabase()
    inserted: list[dict[str, Any]] = []
    for clip in clips[:3]:
        row = clip.to_row(
            user_id=user_id,
            source_video_id=video_id,
            source_channel_id=source_channel_id,
        )
        result = sb.table("ytboost_shorts").insert(row).execute()
        inserted.extend(result.data)
    return inserted
