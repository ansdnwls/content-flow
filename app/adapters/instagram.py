"""Instagram adapter — Reels + Carousel via Graph API."""

from __future__ import annotations

import asyncio
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

GRAPH_API = "https://graph.facebook.com/v21.0"


class InstagramAdapter(PlatformAdapter):
    platform_name = "instagram"

    async def _wait_for_container_ready(
        self,
        client: httpx.AsyncClient,
        container_id: str,
        token: str,
        *,
        attempts: int = 5,
        interval_seconds: float = 1.0,
    ) -> str | None:
        last_status: str | None = None

        for attempt in range(attempts):
            resp = await client.get(
                f"{GRAPH_API}/{container_id}",
                params={"fields": "status_code", "access_token": token},
            )
            if resp.status_code != 200:
                return resp.text

            last_status = resp.json().get("status_code")
            if last_status in {"FINISHED", "PUBLISHED"}:
                return None
            if last_status in {"ERROR", "EXPIRED"}:
                return f"Container status: {last_status}"
            if attempt < attempts - 1:
                await asyncio.sleep(interval_seconds)

        return f"Container status: {last_status or 'UNKNOWN'}"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        ig_user_id = credentials["ig_user_id"]
        caption = options.get("caption", text or "")
        share_to_feed = options.get("share_to_feed", True)

        async with httpx.AsyncClient() as client:
            if len(media) == 1 and media[0].media_type == "video":
                return await self._publish_reel(
                    client, ig_user_id, access_token, media[0], caption, share_to_feed
                )
            elif len(media) > 1:
                return await self._publish_carousel(
                    client, ig_user_id, access_token, media, caption
                )
            elif len(media) == 1 and media[0].media_type == "image":
                return await self._publish_image(
                    client, ig_user_id, access_token, media[0], caption
                )
            return PublishResult(success=False, error="No supported media")

    async def _publish_reel(
        self, client, ig_user_id, token, video: MediaSpec, caption: str, share_to_feed: bool
    ) -> PublishResult:
        # Step 1: Create media container
        resp = await client.post(
            f"{GRAPH_API}/{ig_user_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video.url,
                "caption": caption,
                "share_to_feed": str(share_to_feed).lower(),
                "access_token": token,
            },
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        container_id = resp.json()["id"]

        status_error = await self._wait_for_container_ready(client, container_id, token)
        if status_error:
            return PublishResult(success=False, error=status_error)

        # Step 2: Publish
        pub_resp = await client.post(
            f"{GRAPH_API}/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": token},
        )
        if pub_resp.status_code != 200:
            return PublishResult(success=False, error=pub_resp.text)

        data = pub_resp.json()
        return PublishResult(
            success=True,
            platform_post_id=data["id"],
            raw_response=data,
        )

    async def _publish_carousel(
        self, client, ig_user_id, token, media: list[MediaSpec], caption: str
    ) -> PublishResult:
        children_ids = []
        for m in media:
            media_type = "VIDEO" if m.media_type == "video" else "IMAGE"
            url_key = "video_url" if m.media_type == "video" else "image_url"
            resp = await client.post(
                f"{GRAPH_API}/{ig_user_id}/media",
                params={
                    "media_type": media_type,
                    url_key: m.url,
                    "is_carousel_item": "true",
                    "access_token": token,
                },
            )
            if resp.status_code != 200:
                return PublishResult(success=False, error=f"Carousel item failed: {resp.text}")
            children_ids.append(resp.json()["id"])

        resp = await client.post(
            f"{GRAPH_API}/{ig_user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
                "access_token": token,
            },
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        container_id = resp.json()["id"]
        status_error = await self._wait_for_container_ready(client, container_id, token)
        if status_error:
            return PublishResult(success=False, error=status_error)
        pub_resp = await client.post(
            f"{GRAPH_API}/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": token},
        )
        if pub_resp.status_code != 200:
            return PublishResult(success=False, error=pub_resp.text)

        return PublishResult(success=True, platform_post_id=pub_resp.json()["id"])

    async def _publish_image(
        self, client, ig_user_id, token, image: MediaSpec, caption: str
    ) -> PublishResult:
        resp = await client.post(
            f"{GRAPH_API}/{ig_user_id}/media",
            params={"image_url": image.url, "caption": caption, "access_token": token},
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        container_id = resp.json()["id"]
        status_error = await self._wait_for_container_ready(client, container_id, token)
        if status_error:
            return PublishResult(success=False, error=status_error)
        pub_resp = await client.post(
            f"{GRAPH_API}/{ig_user_id}/media_publish",
            params={"creation_id": container_id, "access_token": token},
        )
        if pub_resp.status_code != 200:
            return PublishResult(success=False, error=pub_resp.text)

        return PublishResult(success=True, platform_post_id=pub_resp.json()["id"])

    async def delete(self, platform_post_id: str, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{GRAPH_API}/{platform_post_id}",
                params={"access_token": credentials["access_token"]},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_API}/me",
                params={"access_token": credentials["access_token"]},
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

        async with httpx.AsyncClient() as client:
            url = f"{GRAPH_API}/{platform_post_id}/comments"
            params: dict[str, str] = {
                "fields": "id,from,text,timestamp",
                "access_token": access_token,
            }
            if since:
                params["since"] = str(int(since.timestamp()))

            while url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    break

                data = resp.json()
                for item in data.get("data", []):
                    created = datetime.fromisoformat(
                        item["timestamp"].replace("Z", "+00:00"),
                    )
                    from_data = item.get("from", {})
                    comments.append(
                        Comment(
                            platform_comment_id=item["id"],
                            author_id=from_data.get("id", ""),
                            author_name=from_data.get("username", ""),
                            text=item.get("text", ""),
                            created_at=created,
                            parent_id=None,
                            raw=item,
                        )
                    )

                paging = data.get("paging", {})
                url = paging.get("next", "")
                params = {}

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
                f"{GRAPH_API}/{comment_id}/replies",
                params={
                    "message": text,
                    "access_token": access_token,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return ReplyResult(
                    success=True,
                    platform_comment_id=data.get("id"),
                )
            return ReplyResult(success=False, error=resp.text)

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        access_token = credentials["access_token"]
        ig_user_id = credentials.get("ig_user_id", "me")
        results: list[AnalyticsData] = []
        async with httpx.AsyncClient() as client:
            if platform_post_id:
                resp = await client.get(
                    f"{GRAPH_API}/{platform_post_id}/insights",
                    params={
                        "metric": "impressions,reach,likes,comments,"
                        "shares,saved",
                        "access_token": access_token,
                    },
                )
                if resp.status_code == 200:
                    metrics: dict[str, int] = {}
                    for entry in resp.json().get("data", []):
                        name = entry.get("name", "")
                        vals = entry.get("values", [{}])
                        metrics[name] = vals[0].get("value", 0)
                    impressions = metrics.get("impressions", 0)
                    reach = metrics.get("reach", 0)
                    likes = metrics.get("likes", 0)
                    comments = metrics.get("comments", 0)
                    shares = metrics.get("shares", 0)
                    total = impressions if impressions > 0 else 1
                    results.append(AnalyticsData(
                        platform="instagram",
                        platform_post_id=platform_post_id,
                        views=impressions,
                        likes=likes,
                        comments=comments,
                        shares=shares,
                        impressions=impressions,
                        reach=reach,
                        engagement_rate=round(
                            (likes + comments + shares)
                            / total * 100,
                            2,
                        ),
                        raw=metrics,
                    ))
            else:
                resp = await client.get(
                    f"{GRAPH_API}/{ig_user_id}",
                    params={
                        "fields": "followers_count,media_count",
                        "access_token": access_token,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results.append(AnalyticsData(
                        platform="instagram",
                        followers=data.get("followers_count", 0),
                        raw=data,
                    ))
        return results
