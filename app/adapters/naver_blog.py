"""Naver Blog adapter — Naver Blog Open API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.adapters.base import (
    AnalyticsData,
    Comment,
    MediaSpec,
    PlatformAdapter,
    PublishResult,
    ReplyResult,
)

NAVER_API = "https://openapi.naver.com"
BLOG_API = f"{NAVER_API}/blog/writePost.json"


class NaverBlogAdapter(PlatformAdapter):
    platform_name = "naver_blog"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        title = options.get("title", "ContentFlow Post")
        category_no = options.get("category_no")

        # Build HTML content with embedded media
        content_parts: list[str] = []
        for m in media:
            if m.media_type == "image":
                content_parts.append(f'<img src="{m.url}" />')
            elif m.media_type == "video":
                content_parts.append(
                    f'<div class="se-video"><video src="{m.url}" controls></video></div>'
                )
        if text:
            content_parts.append(f"<p>{text}</p>")

        body: dict[str, Any] = {
            "title": title,
            "contents": "\n".join(content_parts),
        }
        if category_no:
            body["categoryNo"] = category_no

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(BLOG_API, headers=headers, json=body)

            if resp.status_code != 200:
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            if data.get("error"):
                return PublishResult(
                    success=False,
                    error=data.get("error_description", data["error"]),
                    raw_response=data,
                )

            log_no = str(data.get("logNo", ""))
            blog_id = data.get("blogId", "")
            url = f"https://blog.naver.com/{blog_id}/{log_no}" if blog_id else None

            return PublishResult(
                success=True,
                platform_post_id=log_no,
                url=url,
                raw_response=data,
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        # Naver Blog API does not provide a public delete endpoint
        return False

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{NAVER_API}/v1/nid/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code == 200

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        """Naver Blog has no stable public comment read API for app-managed posts."""
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
            error="TODO: Naver Blog comment reply requires a private or unsupported API",
        )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        """Naver Blog exposes no supported app analytics API in this integration."""
        return []
