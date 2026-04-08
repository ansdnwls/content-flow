"""Kakao adapter — Kakao Story / KakaoTalk Channel posting via Kakao API."""

from __future__ import annotations

from datetime import UTC, datetime
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

KAKAO_API = "https://kapi.kakao.com"


class KakaoAdapter(PlatformAdapter):
    platform_name = "kakao"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Determine target: "story" (default) or "channel"
        target = options.get("target", "story")
        permission = options.get("permission", "A")  # A=all, F=friends, M=me

        async with httpx.AsyncClient(timeout=30.0) as client:
            if target == "channel":
                return await self._post_channel(client, headers, text, media, options)
            return await self._post_story(client, headers, text, media, permission)

    async def _post_story(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        text: str | None,
        media: list[MediaSpec],
        permission: str,
    ) -> PublishResult:
        # Upload images first if present
        image_urls: list[str] = []
        for m in media:
            if m.media_type == "image":
                upload_resp = await client.post(
                    f"{KAKAO_API}/v1/api/story/upload/multi",
                    headers=headers,
                    data={"image_url": m.url},
                )
                if upload_resp.status_code == 200:
                    for item in upload_resp.json():
                        image_urls.append(item.get("url", m.url))

        if image_urls:
            import json as json_mod

            body = {
                "image_url_list": json_mod.dumps(image_urls),
                "content": text or "",
                "permission": permission,
            }
            resp = await client.post(
                f"{KAKAO_API}/v1/api/story/post/photo",
                headers=headers,
                data=body,
            )
        else:
            resp = await client.post(
                f"{KAKAO_API}/v1/api/story/post/note",
                headers=headers,
                data={"content": text or "", "permission": permission},
            )

        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        story_id = data.get("id", "")
        return PublishResult(
            success=True,
            platform_post_id=story_id,
            url=data.get("url"),
            raw_response=data,
        )

    async def _post_channel(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
    ) -> PublishResult:
        # Kakao Channel message via Talk Channel API
        channel_id = options.get("channel_id", "")
        body: dict[str, Any] = {
            "channel_public_id": channel_id,
            "template_object": {
                "object_type": "text",
                "text": text or "",
                "link": {"web_url": options.get("link_url", "")},
            },
        }
        resp = await client.post(
            f"{KAKAO_API}/v1/api/talk/channel/message/send",
            headers=headers,
            json=body,
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        if data.get("result_code") != 0:
            return PublishResult(
                success=False,
                error=data.get("result_message", "Unknown error"),
                raw_response=data,
            )

        return PublishResult(
            success=True,
            platform_post_id=str(data.get("result_code", "")),
            raw_response=data,
        )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{KAKAO_API}/v1/api/story/delete/mystory",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"id": platform_post_id},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{KAKAO_API}/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code == 200

    @staticmethod
    def _parse_comment_time(value: str | None) -> datetime:
        if value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(UTC)

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{KAKAO_API}/v1/api/talk/channel/messages/{platform_post_id}/comments",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"since": since.isoformat()} if since else None,
            )
            if resp.status_code != 200:
                return []

            comments: list[Comment] = []
            for item in resp.json().get("comments", []):
                created_at = self._parse_comment_time(item.get("created_at"))
                comments.append(
                    Comment(
                        platform_comment_id=str(item.get("id", "")),
                        author_id=str(item.get("user_id", "")),
                        author_name=item.get("nickname", ""),
                        text=item.get("text", ""),
                        created_at=created_at,
                        parent_id=item.get("parent_id"),
                        raw=item,
                    )
                )
            return comments

    async def reply_comment(
        self,
        platform_post_id: str,
        comment_id: str,
        text: str,
        credentials: dict[str, str],
    ) -> ReplyResult:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{KAKAO_API}/v1/api/talk/channel/messages/{platform_post_id}/comments/{comment_id}/reply",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"text": text},
            )
            if resp.status_code != 200:
                return ReplyResult(success=False, error=resp.text)

            data = resp.json()
            return ReplyResult(
                success=True,
                platform_comment_id=str(data.get("id", "")),
            )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            if platform_post_id:
                resp = await client.get(
                    f"{KAKAO_API}/v1/api/talk/channel/messages/{platform_post_id}/insights",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code != 200:
                    return []

                metrics = resp.json()
                views = int(metrics.get("view_count", 0))
                likes = int(metrics.get("like_count", 0))
                comments = int(metrics.get("comment_count", 0))
                shares = int(metrics.get("share_count", 0))
                denominator = views if views > 0 else 1
                return [
                    AnalyticsData(
                        platform=self.platform_name,
                        platform_post_id=platform_post_id,
                        views=views,
                        likes=likes,
                        comments=comments,
                        shares=shares,
                        impressions=views,
                        engagement_rate=round(
                            (likes + comments + shares) / denominator * 100,
                            2,
                        ),
                        raw=metrics,
                    )
                ]

            resp = await client.get(
                f"{KAKAO_API}/v1/api/talk/channel/insights",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                return []

            metrics = resp.json()
            return [
                AnalyticsData(
                    platform=self.platform_name,
                    followers=int(metrics.get("subscriber_count", 0)),
                    raw=metrics,
                )
            ]
