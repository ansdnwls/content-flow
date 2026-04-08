"""TikTok adapter — Content Posting API."""

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

TIKTOK_API = "https://open.tiktokapis.com/v2"
TIKTOK_PRIVACY_LEVELS = {
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "SELF_ONLY",
}


class TikTokAdapter(PlatformAdapter):
    platform_name = "tiktok"

    @staticmethod
    def _build_source_info(video: MediaSpec, options: dict[str, Any]) -> dict[str, Any]:
        source = options.get("source", "PULL_FROM_URL")
        if source == "PULL_FROM_URL":
            return {
                "source": "PULL_FROM_URL",
                "video_url": video.url,
            }
        return {
            "source": "FILE_UPLOAD",
            "video_size": options.get("video_size"),
            "chunk_size": options.get("chunk_size"),
            "total_chunk_count": options.get("total_chunk_count"),
        }

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        video = next((m for m in media if m.media_type == "video"), None)
        if not video:
            return PublishResult(success=False, error="No video provided")

        privacy_level = options.get("privacy_level", "PUBLIC_TO_EVERYONE")
        if privacy_level not in TIKTOK_PRIVACY_LEVELS:
            allowed = ", ".join(sorted(TIKTOK_PRIVACY_LEVELS))
            return PublishResult(
                success=False,
                error=f"privacy_level must be one of: {allowed}",
            )

        async with httpx.AsyncClient() as client:
            # Step 1: Init upload
            init_resp = await client.post(
                f"{TIKTOK_API}/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                json={
                    "post_info": {
                        "title": options.get("title", text or ""),
                        "privacy_level": privacy_level,
                        "disable_comment": options.get("disable_comment", False),
                        "disable_duet": options.get("disable_duet", False),
                        "disable_stitch": options.get("disable_stitch", False),
                        "video_cover_timestamp_ms": options.get("video_cover_timestamp_ms"),
                    },
                    "source_info": self._build_source_info(video, options),
                },
            )

            if init_resp.status_code != 200:
                return PublishResult(success=False, error=init_resp.text)

            data = init_resp.json()
            publish_id = data.get("data", {}).get("publish_id")
            if not publish_id:
                return PublishResult(success=False, error="TikTok response missing publish_id")
            return PublishResult(
                success=True,
                platform_post_id=publish_id,
                raw_response=data,
            )

    async def delete(self, platform_post_id: str, credentials: dict[str, str]) -> bool:
        # TikTok Content Posting API does not support deletion
        return False

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{TIKTOK_API}/user/info/",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
                params={"fields": "display_name"},
            )
            return resp.status_code == 200

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        access_token = credentials["access_token"]
        comments: list[Comment] = []
        cursor: int | None = None

        async with httpx.AsyncClient() as client:
            while True:
                body: dict[str, Any] = {
                    "video_id": platform_post_id,
                    "max_count": 50,
                }
                if cursor is not None:
                    body["cursor"] = cursor

                resp = await client.post(
                    f"{TIKTOK_API}/comment/list/",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=body,
                )
                if resp.status_code != 200:
                    break

                data = resp.json().get("data", {})
                for item in data.get("comments", []):
                    created = datetime.fromtimestamp(
                        item.get("create_time", 0),
                    )
                    if since and created <= since:
                        return comments
                    comments.append(
                        Comment(
                            platform_comment_id=item["id"],
                            author_id=item.get("user", {}).get("id", ""),
                            author_name=item.get("user", {}).get(
                                "display_name", "",
                            ),
                            text=item.get("text", ""),
                            created_at=created,
                            parent_id=item.get("parent_comment_id"),
                            raw=item,
                        )
                    )

                if not data.get("has_more", False):
                    break
                cursor = data.get("cursor")

        return comments

    async def reply_comment(
        self,
        platform_post_id: str,
        comment_id: str,
        text: str,
        credentials: dict[str, str],
    ) -> ReplyResult:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TIKTOK_API}/comment/reply/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "video_id": platform_post_id,
                    "comment_id": comment_id,
                    "text": text,
                },
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return ReplyResult(
                    success=True,
                    platform_comment_id=data.get("comment_id"),
                )
            return ReplyResult(success=False, error=resp.text)

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        access_token = credentials["access_token"]
        results: list[AnalyticsData] = []
        async with httpx.AsyncClient() as client:
            if platform_post_id:
                resp = await client.post(
                    f"{TIKTOK_API}/video/query/",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "filters": {"video_ids": [platform_post_id]},
                        "fields": [
                            "id", "view_count", "like_count",
                            "comment_count", "share_count",
                        ],
                    },
                )
                if resp.status_code == 200:
                    for v in resp.json().get("data", {}).get(
                        "videos", [],
                    ):
                        views = v.get("view_count", 0)
                        likes = v.get("like_count", 0)
                        comments = v.get("comment_count", 0)
                        shares = v.get("share_count", 0)
                        total = views if views > 0 else 1
                        results.append(AnalyticsData(
                            platform="tiktok",
                            platform_post_id=v.get("id"),
                            views=views,
                            likes=likes,
                            comments=comments,
                            shares=shares,
                            engagement_rate=round(
                                (likes + comments + shares)
                                / total * 100,
                                2,
                            ),
                            raw=v,
                        ))
            else:
                resp = await client.get(
                    f"{TIKTOK_API}/user/info/",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "fields": "follower_count,following_count,"
                        "likes_count,video_count",
                    },
                )
                if resp.status_code == 200:
                    user = resp.json().get("data", {}).get("user", {})
                    results.append(AnalyticsData(
                        platform="tiktok",
                        followers=user.get("follower_count", 0),
                        likes=user.get("likes_count", 0),
                        raw=user,
                    ))
        return results
