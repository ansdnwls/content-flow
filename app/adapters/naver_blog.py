"""Naver Blog adapter — Playwright browser automation.

The official Naver Blog Write API has been deprecated.
This adapter uses Playwright with stealth to automate posting
through the blog editor UI.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.adapters.base import (
    AnalyticsData,
    Comment,
    MediaSpec,
    PlatformAdapter,
    PublishResult,
    ReplyResult,
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class NaverBlogAdapter(PlatformAdapter):
    platform_name = "naver_blog"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        from app.services.naver_blog_playwright import NaverBlogPlaywright

        title = options.get("title", "ContentFlow Post")
        tags = options.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        blog_id = (
            options.get("blog_id")
            or credentials.get("handle")
            or credentials.get("blog_id")
        )

        image_urls = [m.url for m in media if m.media_type == "image"]

        pw_client = NaverBlogPlaywright(blog_id=blog_id)

        if not pw_client.has_session():
            return PublishResult(
                success=False,
                error="No Naver session file. Run setup_session() first.",
            )

        result = await pw_client.post(
            title=title,
            content=text or "",
            images=image_urls,
            tags=tags,
        )

        if result.get("success"):
            return PublishResult(
                success=True,
                url=result.get("url"),
                raw_response=result,
            )

        return PublishResult(
            success=False,
            error=result.get("error", "Unknown Playwright error"),
            raw_response=result,
        )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        return False

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        """Check if Naver session file exists and is not empty."""
        from app.services.naver_blog_playwright import NaverBlogPlaywright

        blog_id = credentials.get("handle") or credentials.get("blog_id")
        pw_client = NaverBlogPlaywright(blog_id=blog_id)
        return pw_client.has_session()

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        return []

    async def reply_comment(
        self,
        platform_post_id: str,
        comment_id: str,
        text: str,
        credentials: dict[str, str],
    ) -> ReplyResult:
        return ReplyResult(
            success=False,
            error="Naver Blog comment reply not supported via Playwright automation",
        )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        return []
