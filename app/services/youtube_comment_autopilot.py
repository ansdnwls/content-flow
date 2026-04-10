"""YtBoost-specific YouTube comment autopilot."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.adapters.youtube import YouTubeAdapter
from app.config import get_settings
from app.core.db import get_supabase
from app.oauth.token_store import get_valid_credentials
from app.services.comment_service import CommentService

logger = logging.getLogger(__name__)

MIN_SAMPLES_FOR_LEARNING = 10
MAX_SAMPLES_FOR_LEARNING = 100

TONE_ANALYSIS_PROMPT = """\
You are a tone analyst. Analyze the following YouTube comment replies from a creator \
and produce a JSON object describing their communication style.

Replies:
{replies_text}

Return ONLY a JSON object with these exact fields:
- "average_length": integer, average character count per reply
- "emoji_frequency": float 0-1, how often emojis appear (0=never, 1=every reply)
- "greeting_patterns": list of up to 3 common greeting phrases (e.g. ["감사합니다!", "안녕하세요"])
- "formality": one of "formal", "casual", "mixed"
- "representative_phrases": list of exactly 5 characteristic expressions
- "style_summary": one sentence describing overall tone

JSON only, no markdown fences."""


class ChannelTone(BaseModel):
    """Learned communication style for a YouTube channel's replies."""

    average_length: int = 0
    emoji_frequency: float = 0.0
    greeting_patterns: list[str] = Field(default_factory=list)
    formality: str = "casual"
    representative_phrases: list[str] = Field(default_factory=list)
    style_summary: str = "friendly concise"
    sample_size: int = 0


class ToneLearningError(Exception):
    """Raised when tone learning fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


async def _analyze_tone_with_claude(replies: list[str]) -> dict[str, Any]:
    """Call Claude API to analyze reply tone. Raises on failure."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise ToneLearningError("ANTHROPIC_API_KEY not configured")

    replies_text = "\n---\n".join(replies[:MAX_SAMPLES_FOR_LEARNING])
    prompt = TONE_ANALYSIS_PROMPT.format(replies_text=replies_text)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.anthropic_api_base_url.rstrip('/')}/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        payload = response.json()
        text_parts = [
            p["text"]
            for p in payload.get("content", [])
            if p.get("type") == "text"
        ]
        raw_text = "".join(text_parts).strip()
        return json.loads(raw_text)


async def list_recent_video_ids(channel_id: str, *, access_token: str) -> list[str]:
    """Fetch recent YouTube uploads for a channel."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "id",
                "channelId": channel_id,
                "type": "video",
                "order": "date",
                "maxResults": 5,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return [
            item["id"]["videoId"]
            for item in response.json().get("items", [])
            if item.get("id", {}).get("videoId")
        ]


class YouTubeCommentAutopilot:
    def __init__(self) -> None:
        self.comment_service = CommentService()

    async def learn_channel_tone(self, channel_id: str, user_id: str) -> ChannelTone:
        """Analyze prior replies with Claude to learn channel communication style.

        Requires at least MIN_SAMPLES_FOR_LEARNING (10) replies.
        Caps at MAX_SAMPLES_FOR_LEARNING (100) to control cost.
        """
        sb = get_supabase()
        comments = (
            sb.table("comments")
            .select("text, ai_reply")
            .eq("user_id", user_id)
            .eq("platform", "youtube")
            .execute()
            .data
        )
        replies = [row["ai_reply"] for row in comments if row.get("ai_reply")]
        sample_size = len(replies)

        if sample_size < MIN_SAMPLES_FOR_LEARNING:
            raise ToneLearningError(
                f"Not enough reply samples: {sample_size} < {MIN_SAMPLES_FOR_LEARNING}"
            )

        analysis = await _analyze_tone_with_claude(replies[:MAX_SAMPLES_FOR_LEARNING])

        tone = ChannelTone(
            average_length=analysis.get("average_length", 0),
            emoji_frequency=analysis.get("emoji_frequency", 0.0),
            greeting_patterns=analysis.get("greeting_patterns", []),
            formality=analysis.get("formality", "casual"),
            representative_phrases=analysis.get("representative_phrases", []),
            style_summary=analysis.get("style_summary", "friendly concise"),
            sample_size=min(sample_size, MAX_SAMPLES_FOR_LEARNING),
        )

        profile = tone.model_dump(exclude={"sample_size"})
        sb.table("ytboost_channel_tones").upsert(
            {
                "user_id": user_id,
                "youtube_channel_id": channel_id,
                "tone_profile": profile,
                "sample_size": tone.sample_size,
            },
            on_conflict="user_id,youtube_channel_id",
        ).execute()

        return tone

    def _build_tone_context(self, tone: ChannelTone) -> str:
        """Build a system prompt snippet from a learned tone."""
        parts = [
            f"Reply style: {tone.style_summary}.",
            f"Formality: {tone.formality}.",
            f"Target length: ~{tone.average_length} chars.",
        ]
        if tone.greeting_patterns:
            parts.append(f"Common greetings: {', '.join(tone.greeting_patterns)}.")
        if tone.representative_phrases:
            parts.append(
                f"Characteristic phrases: {', '.join(tone.representative_phrases)}."
            )
        if tone.emoji_frequency > 0.3:
            parts.append("Use emojis occasionally.")
        elif tone.emoji_frequency < 0.1:
            parts.append("Avoid emojis.")
        return " ".join(parts)

    async def get_stored_tone(self, channel_id: str, user_id: str) -> ChannelTone | None:
        """Load previously learned tone from DB, if any."""
        sb = get_supabase()
        response = sb.table("ytboost_channel_tones").select("*").eq("user_id", user_id).eq("youtube_channel_id", channel_id).limit(1).execute()
        rows = getattr(response, "data", None) or []
        row = rows[0] if rows else None
        if not row:
            return None
        profile = row.get("tone_profile") or {}
        return ChannelTone(
            average_length=profile.get("average_length", 0),
            emoji_frequency=profile.get("emoji_frequency", 0.0),
            greeting_patterns=profile.get("greeting_patterns", []),
            formality=profile.get("formality", "casual"),
            representative_phrases=profile.get("representative_phrases", []),
            style_summary=profile.get("style_summary", "friendly concise"),
            sample_size=row.get("sample_size", 0),
        )

    async def run_for_channel(
        self,
        channel_id: str,
        user_id: str,
        *,
        mode: str = "review",
        account_id: str | None = None,
        recent_video_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """Collect recent comments and either queue or auto-send replies."""
        sb = get_supabase()
        account = None
        if account_id:
            response = sb.table("social_accounts").select("id").eq("id", account_id).eq("owner_id", user_id).limit(1).execute()
            rows = getattr(response, "data", None) or []
            account = rows[0] if rows else None
        if account is None:
            response = sb.table("social_accounts").select("id").eq("owner_id", user_id).eq("platform", "youtube").limit(1).execute()
            rows = getattr(response, "data", None) or []
            account = rows[0] if rows else None
        if not account:
            return {"collected": 0, "prepared": 0, "replied": 0}

        credentials = await get_valid_credentials(account["id"], user_id)
        video_ids = recent_video_ids or await list_recent_video_ids(
            channel_id,
            access_token=credentials["access_token"],
        )

        tone = await self.get_stored_tone(channel_id, user_id)
        context = self._build_tone_context(tone) if tone else ""
        prepared = 0
        replied = 0
        collected = 0

        for video_id in video_ids:
            stored = await self.comment_service.collect_comments(
                user_id=user_id,
                platform="youtube",
                platform_post_id=video_id,
                credentials=credentials,
            )
            collected += len(stored)

            pending_rows = (
                sb.table("comments")
                .select("*")
                .eq("user_id", user_id)
                .eq("platform", "youtube")
                .eq("platform_post_id", video_id)
                .eq("reply_status", "pending")
                .execute()
                .data
            )

            for comment in pending_rows:
                if mode == "auto":
                    result = await self.comment_service.auto_reply(
                        comment_id=comment["id"],
                        user_id=user_id,
                        credentials=credentials,
                        context=context,
                    )
                    if result.get("success"):
                        replied += 1
                else:
                    ai_reply = await self.comment_service.generate_reply(
                        comment["text"],
                        context=context,
                    )
                    sb.table("comments").update(
                        {"ai_reply": ai_reply, "reply_status": "review_pending"},
                    ).eq("id", comment["id"]).execute()
                    prepared += 1

        return {"collected": collected, "prepared": prepared, "replied": replied}

    async def approve_reply(
        self,
        comment_id: str,
        user_id: str,
        *,
        text: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an approved or edited reply to YouTube."""
        sb = get_supabase()
        response = sb.table("comments").select("*").eq("id", comment_id).eq("user_id", user_id).limit(1).execute()
        rows = getattr(response, "data", None) or []
        comment = rows[0] if rows else None
        if not comment:
            return {"success": False, "error": "Comment not found"}

        account = None
        if account_id:
            response = sb.table("social_accounts").select("id").eq("id", account_id).eq("owner_id", user_id).limit(1).execute()
            rows = getattr(response, "data", None) or []
            account = rows[0] if rows else None
        if account is None:
            response = sb.table("social_accounts").select("id").eq("owner_id", user_id).eq("platform", "youtube").limit(1).execute()
            rows = getattr(response, "data", None) or []
            account = rows[0] if rows else None
        if not account:
            return {"success": False, "error": "YouTube account not found"}

        reply_text = text or comment.get("ai_reply") or ""
        if not reply_text:
            return {"success": False, "error": "Reply text is empty"}

        credentials = await get_valid_credentials(account["id"], user_id)
        adapter = YouTubeAdapter()
        result = await adapter.reply_comment(
            comment["platform_post_id"],
            comment["platform_comment_id"],
            reply_text,
            credentials,
        )
        if result.success:
            sb.table("comments").update(
                {
                    "ai_reply": reply_text,
                    "reply_status": "replied",
                    "platform_reply_id": result.platform_comment_id,
                },
            ).eq("id", comment_id).execute()
        return {
            "success": result.success,
            "platform_reply_id": result.platform_comment_id,
            "error": result.error,
            "ai_reply": reply_text,
        }
