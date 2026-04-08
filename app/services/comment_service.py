"""Comment collection and AI-powered reply generation service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.adapters.base import PlatformAdapter, ReplyResult
from app.config import get_settings
from app.core.db import get_supabase

ADAPTER_MAP: dict[str, type[PlatformAdapter]] = {}


def _get_adapter_map() -> dict[str, type[PlatformAdapter]]:
    """Lazy-load adapter map to avoid circular imports."""
    if not ADAPTER_MAP:
        from app.adapters.instagram import InstagramAdapter
        from app.adapters.tiktok import TikTokAdapter
        from app.adapters.youtube import YouTubeAdapter

        ADAPTER_MAP.update(
            {
                "youtube": YouTubeAdapter,
                "tiktok": TikTokAdapter,
                "instagram": InstagramAdapter,
            }
        )
    return ADAPTER_MAP


class CommentService:
    """Collects comments from platforms and generates AI replies."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def collect_comments(
        self,
        user_id: str,
        platform: str,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[dict]:
        """Fetch comments from platform and upsert into DB."""
        adapters = _get_adapter_map()
        adapter_cls = adapters.get(platform)
        if not adapter_cls:
            return []

        adapter = adapter_cls()
        comments = await adapter.get_comments(
            platform_post_id, credentials, since=since,
        )

        sb = get_supabase()
        stored: list[dict] = []
        for comment in comments:
            row = {
                "user_id": user_id,
                "platform": platform,
                "platform_post_id": platform_post_id,
                "platform_comment_id": comment.platform_comment_id,
                "author_id": comment.author_id,
                "author_name": comment.author_name,
                "text": comment.text,
                "comment_created_at": comment.created_at.isoformat(),
                "ai_reply": None,
                "reply_status": "pending",
                "platform_reply_id": None,
            }
            result = (
                sb.table("comments")
                .upsert(row, on_conflict="platform_comment_id")
                .execute()
            )
            stored.extend(result.data)

        return stored

    async def generate_reply(self, comment_text: str, context: str = "") -> str:
        """Generate an AI reply for a comment using Claude API."""
        if not self.settings.anthropic_api_key:
            return self._fallback_reply(comment_text)

        try:
            return await self._generate_with_claude(comment_text, context)
        except httpx.HTTPError:
            return self._fallback_reply(comment_text)

    async def _generate_with_claude(
        self, comment_text: str, context: str,
    ) -> str:
        prompt = self._build_reply_prompt(comment_text, context)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.settings.anthropic_api_base_url.rstrip('/')}/messages",
                headers={
                    "x-api-key": self.settings.anthropic_api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.settings.anthropic_model,
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
            parts = [
                p["text"]
                for p in payload.get("content", [])
                if p.get("type") == "text"
            ]
            return "".join(parts).strip() or self._fallback_reply(comment_text)

    @staticmethod
    def _build_reply_prompt(comment_text: str, context: str) -> str:
        ctx_line = f"\nPost context: {context}" if context else ""
        return (
            "You are a friendly social media community manager. "
            "Reply to the following comment in a helpful, authentic tone. "
            "Keep your reply concise (under 200 characters). "
            "Do not use hashtags or emojis unless the comment uses them."
            f"{ctx_line}\n\nComment: {comment_text}\n\nReply:"
        )

    @staticmethod
    def _fallback_reply(comment_text: str) -> str:
        if "?" in comment_text:
            return "Great question! We'll look into this and get back to you soon."
        return "Thanks for your comment! We appreciate your engagement."

    async def auto_reply(
        self,
        comment_id: str,
        user_id: str,
        credentials: dict[str, str],
        context: str = "",
    ) -> dict[str, Any]:
        """Generate an AI reply and post it to the platform."""
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

        if comment.get("reply_status") == "replied":
            return {"success": False, "error": "Already replied"}

        reply_text = await self.generate_reply(comment["text"], context)

        adapters = _get_adapter_map()
        adapter_cls = adapters.get(comment["platform"])
        if not adapter_cls:
            sb.table("comments").update(
                {"ai_reply": reply_text, "reply_status": "skipped"},
            ).eq("id", comment_id).execute()
            return {
                "success": False,
                "error": f"No adapter for {comment['platform']}",
                "ai_reply": reply_text,
            }

        adapter = adapter_cls()
        result: ReplyResult = await adapter.reply_comment(
            comment["platform_post_id"],
            comment["platform_comment_id"],
            reply_text,
            credentials,
        )

        new_status = "replied" if result.success else "failed"
        sb.table("comments").update(
            {
                "ai_reply": reply_text,
                "reply_status": new_status,
                "platform_reply_id": result.platform_comment_id,
            },
        ).eq("id", comment_id).execute()

        return {
            "success": result.success,
            "ai_reply": reply_text,
            "platform_reply_id": result.platform_comment_id,
            "error": result.error,
        }

    async def list_comments(
        self,
        user_id: str,
        platform: str | None = None,
        platform_post_id: str | None = None,
        reply_status: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """List comments with optional filters and pagination."""
        sb = get_supabase()
        query = sb.table("comments").select("*", count="exact").eq(
            "user_id", user_id,
        )
        if platform:
            query = query.eq("platform", platform)
        if platform_post_id:
            query = query.eq("platform_post_id", platform_post_id)
        if reply_status:
            query = query.eq("reply_status", reply_status)

        start = (page - 1) * limit
        end = start + limit - 1
        result = query.order("created_at", desc=True).range(start, end).execute()
        return result.data, result.count or 0

    async def get_comment(self, comment_id: str, user_id: str) -> dict | None:
        """Get a single comment by ID."""
        sb = get_supabase()
        result = (
            sb.table("comments")
            .select("*")
            .eq("id", comment_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data
