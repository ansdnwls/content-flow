"""YouTube transcript extraction service using youtube-transcript-api."""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class TranscriptError(Exception):
    """Raised when transcript extraction fails."""
    pass


def extract_video_id(url_or_id: str) -> str:
    """
    Extract YouTube video ID from URL or return as-is if already an ID.
    
    Supported formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtu.be/VIDEO_ID?si=...
    - https://www.youtube.com/shorts/VIDEO_ID
    - https://m.youtube.com/watch?v=VIDEO_ID
    - VIDEO_ID (11자 ID 그대로)
    
    Raises:
        TranscriptError: If video ID cannot be extracted
    """
    if not url_or_id:
        raise TranscriptError("Empty URL or ID")
    
    # 이미 ID 형식이면 그대로 반환 (11자, 슬래시 없음)
    if len(url_or_id) == 11 and "/" not in url_or_id and "." not in url_or_id:
        return url_or_id
    
    try:
        parsed = urlparse(url_or_id)
    except Exception as exc:
        raise TranscriptError(f"Invalid URL: {url_or_id}") from exc
    
    # youtu.be/VIDEO_ID (쿼리스트링 si=... 무시됨)
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        video_id = parsed.path.lstrip("/")
        if video_id:
            return video_id
    
    # youtube.com 계열
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        # /watch?v=VIDEO_ID
        if parsed.path == "/watch":
            query = parse_qs(parsed.query)
            if "v" in query and query["v"]:
                return query["v"][0]
        
        # /shorts/VIDEO_ID
        if parsed.path.startswith("/shorts/"):
            parts = parsed.path.split("/")
            if len(parts) >= 3 and parts[2]:
                return parts[2]
        
        # /embed/VIDEO_ID
        if parsed.path.startswith("/embed/"):
            parts = parsed.path.split("/")
            if len(parts) >= 3 and parts[2]:
                return parts[2]
    
    raise TranscriptError(f"Cannot extract video ID from: {url_or_id}")


def fetch_transcript(
    video_url_or_id: str,
    languages: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch transcript for a YouTube video.
    
    Uses youtube-transcript-api 1.x API (instance-based).
    
    Args:
        video_url_or_id: YouTube URL or video ID
        languages: Preferred languages in order (default: ["ko", "en"])
    
    Returns:
        List of transcript segments in format compatible with shorts_extractor:
        [{"start": int, "end": int, "text": str}, ...]
    
    Raises:
        TranscriptError: If transcript cannot be fetched for any reason
    """
    video_id = extract_video_id(video_url_or_id)
    languages = languages or ["ko", "en"]
    
    logger.info(
        "transcript_fetch_start",
        video_id=video_id,
        languages=languages,
    )
    
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
    except TranscriptsDisabled:
        logger.warning("transcript_disabled", video_id=video_id)
        raise TranscriptError(f"Transcripts disabled for video {video_id}")
    except NoTranscriptFound:
        logger.warning(
            "transcript_not_found",
            video_id=video_id,
            languages=languages,
        )
        raise TranscriptError(
            f"No transcript found for video {video_id} in languages {languages}"
        )
    except VideoUnavailable:
        logger.warning("video_unavailable", video_id=video_id)
        raise TranscriptError(f"Video {video_id} unavailable")
    except Exception as exc:
        logger.error(
            "transcript_fetch_failed",
            video_id=video_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise TranscriptError(f"Failed to fetch transcript: {exc}") from exc
    
    # 1.x API는 FetchedTranscriptSnippet 객체 리스트 반환
    # 객체 속성: text, start, duration
    segments: list[dict[str, Any]] = []
    for snippet in fetched:
        start = int(snippet.start)
        end = int(snippet.start + snippet.duration)
        segments.append({
            "start": start,
            "end": end,
            "text": snippet.text,
        })
    
    logger.info(
        "transcript_fetch_success",
        video_id=video_id,
        segment_count=len(segments),
    )
    
    return segments


def get_video_duration(transcript: list[dict[str, Any]]) -> int:
    """Get total duration in seconds from transcript."""
    if not transcript:
        return 0
    return max(seg["end"] for seg in transcript)


def list_available_languages(video_url_or_id: str) -> list[dict[str, str]]:
    """
    List available transcript languages for a video.
    
    Returns:
        List of {"language": "...", "language_code": "...", "is_generated": bool}
    """
    video_id = extract_video_id(video_url_or_id)
    
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
    except Exception as exc:
        raise TranscriptError(f"Failed to list transcripts: {exc}") from exc
    
    result = []
    for transcript in transcript_list:
        result.append({
            "language": transcript.language,
            "language_code": transcript.language_code,
            "is_generated": transcript.is_generated,
        })
    
    return result