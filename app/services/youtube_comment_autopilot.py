"""YtBoost-specific YouTube comment autopilot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.adapters.youtube import YouTubeAdapter
from app.core.db import get_supabase
from app.oauth.token_store import get_valid_credentials
from app.services.comment_service import CommentService


@dataclass(frozen=True)
class ChannelTone:
    tone_profile: dict[str, Any]
    sample_size: int


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
        """Infer a lightweight tone profile from prior AI or manual replies."""
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

        avg_length = (
            round(sum(len(reply) for reply in replies) / sample_size, 2)
            if sample_size
            else 0.0
        )
        profile = {
            "average_reply_length": avg_length,
            "uses_questions": any("?" in reply for reply in replies),
            "style": "friendly concise" if sample_size else "friendly concise",
        }

        result = (
            sb.table("ytboost_channel_tones")
            .upsert(
                {
                    "user_id": user_id,
                    "youtube_channel_id": channel_id,
                    "tone_profile": profile,
                    "sample_size": sample_size,
                },
                on_conflict="user_id,youtube_channel_id",
            )
            .execute()
        )
        row = result.data[0]
        return ChannelTone(
            tone_profile=row.get("tone_profile") or profile,
            sample_size=row.get("sample_size", sample_size),
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
            account = (
                sb.table("social_accounts")
                .select("id")
                .eq("id", account_id)
                .eq("owner_id", user_id)
                .maybe_single()
                .execute()
                .data
            )
        if account is None:
            account = (
                sb.table("social_accounts")
                .select("id")
                .eq("owner_id", user_id)
                .eq("platform", "youtube")
                .maybe_single()
                .execute()
                .data
            )
        if not account:
            return {"collected": 0, "prepared": 0, "replied": 0}

        credentials = await get_valid_credentials(account["id"], user_id)
        video_ids = recent_video_ids or await list_recent_video_ids(
            channel_id,
            access_token=credentials["access_token"],
        )

        tone = await self.learn_channel_tone(channel_id, user_id)
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
                context = (
                    f"Channel tone: {tone.tone_profile.get('style', 'friendly concise')}. "
                    f"Average reply length: {tone.tone_profile.get('average_reply_length', 0)}."
                )
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
        comment = (
            sb.table("comments")
            .select("*")
            .eq("id", comment_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
            .data
        )
        if not comment:
            return {"success": False, "error": "Comment not found"}

        account = None
        if account_id:
            account = (
                sb.table("social_accounts")
                .select("id")
                .eq("id", account_id)
                .eq("owner_id", user_id)
                .maybe_single()
                .execute()
                .data
            )
        if account is None:
            account = (
                sb.table("social_accounts")
                .select("id")
                .eq("owner_id", user_id)
                .eq("platform", "youtube")
                .maybe_single()
                .execute()
                .data
            )
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
