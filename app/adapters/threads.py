"""Threads adapter — Threads Publishing API (Meta)."""

from __future__ import annotations

import asyncio
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

THREADS_API = "https://graph.threads.net/v1.0"

# Container status polling
_POLL_INTERVAL_SEC = 2
_MAX_POLL_ATTEMPTS = 30


class ThreadsAdapter(PlatformAdapter):
    platform_name = "threads"

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime:
        if value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(UTC)

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        user_id = credentials["threads_user_id"]

        async with httpx.AsyncClient(timeout=60.0) as client:
            if len(media) > 1:
                return await self._publish_carousel(
                    client, user_id, access_token, text, media, options
                )
            return await self._publish_single(
                client, user_id, access_token, text, media, options
            )

    async def _publish_single(
        self, client, user_id, token, text, media: list[MediaSpec], options
    ) -> PublishResult:
        """Publish a single text, image, or video thread."""
        container_params: dict[str, Any] = {"access_token": token}

        if text:
            container_params["text"] = text

        reply_control = options.get("reply_control")
        if reply_control:
            container_params["reply_control"] = reply_control

        if media:
            m = media[0]
            if m.media_type == "video":
                container_params["media_type"] = "VIDEO"
                container_params["video_url"] = m.url
            elif m.media_type == "image":
                container_params["media_type"] = "IMAGE"
                container_params["image_url"] = m.url
        else:
            container_params["media_type"] = "TEXT"

        # Step 1: Create container
        resp = await client.post(
            f"{THREADS_API}/{user_id}/threads",
            params=container_params,
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        container_id = resp.json().get("id")
        if not container_id:
            return PublishResult(success=False, error="No container ID returned")

        # Step 2: Wait for container to be ready (video processing)
        if media and media[0].media_type == "video":
            ready = await self._poll_container(client, container_id, token)
            if not ready:
                return PublishResult(
                    success=False, error="Container processing timed out"
                )

        # Step 3: Publish
        pub_resp = await client.post(
            f"{THREADS_API}/{user_id}/threads_publish",
            params={"creation_id": container_id, "access_token": token},
        )
        if pub_resp.status_code != 200:
            return PublishResult(success=False, error=pub_resp.text)

        data = pub_resp.json()
        thread_id = data.get("id", "")
        return PublishResult(
            success=True,
            platform_post_id=thread_id,
            url=f"https://www.threads.net/post/{thread_id}",
            raw_response=data,
        )

    async def _publish_carousel(
        self, client, user_id, token, text, media: list[MediaSpec], options
    ) -> PublishResult:
        """Publish a carousel thread with multiple media items."""
        children_ids = []

        # Create child containers
        for m in media:
            params: dict[str, Any] = {
                "is_carousel_item": "true",
                "access_token": token,
            }
            if m.media_type == "video":
                params["media_type"] = "VIDEO"
                params["video_url"] = m.url
            else:
                params["media_type"] = "IMAGE"
                params["image_url"] = m.url

            resp = await client.post(
                f"{THREADS_API}/{user_id}/threads",
                params=params,
            )
            if resp.status_code != 200:
                return PublishResult(
                    success=False, error=f"Carousel item failed: {resp.text}"
                )
            child_id = resp.json().get("id")
            if not child_id:
                return PublishResult(success=False, error="No child container ID")
            children_ids.append(child_id)

        # Wait for video containers
        for i, m in enumerate(media):
            if m.media_type == "video":
                ready = await self._poll_container(client, children_ids[i], token)
                if not ready:
                    return PublishResult(
                        success=False,
                        error=f"Carousel video {i} processing timed out",
                    )

        # Create carousel container
        carousel_params: dict[str, Any] = {
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "access_token": token,
        }
        if text:
            carousel_params["text"] = text

        resp = await client.post(
            f"{THREADS_API}/{user_id}/threads",
            params=carousel_params,
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        container_id = resp.json().get("id")

        # Publish carousel
        pub_resp = await client.post(
            f"{THREADS_API}/{user_id}/threads_publish",
            params={"creation_id": container_id, "access_token": token},
        )
        if pub_resp.status_code != 200:
            return PublishResult(success=False, error=pub_resp.text)

        data = pub_resp.json()
        thread_id = data.get("id", "")
        return PublishResult(
            success=True,
            platform_post_id=thread_id,
            url=f"https://www.threads.net/post/{thread_id}",
            raw_response=data,
        )

    async def _poll_container(
        self, client: httpx.AsyncClient, container_id: str, token: str
    ) -> bool:
        """Poll container status until FINISHED or timeout."""
        for _ in range(_MAX_POLL_ATTEMPTS):
            resp = await client.get(
                f"{THREADS_API}/{container_id}",
                params={"fields": "status", "access_token": token},
            )
            if resp.status_code == 200:
                status = resp.json().get("status")
                if status == "FINISHED":
                    return True
                if status == "ERROR":
                    return False
            await asyncio.sleep(_POLL_INTERVAL_SEC)
        return False

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        # Threads API does not currently support programmatic deletion
        return False

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{THREADS_API}/me",
                params={
                    "fields": "id,username",
                    "access_token": credentials["access_token"],
                },
            )
            return resp.status_code == 200

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        comments: list[Comment] = []
        url = f"{THREADS_API}/{platform_post_id}/replies"
        params: dict[str, Any] = {
            "fields": "id,text,username,timestamp,reply_to_id",
            "access_token": credentials["access_token"],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    break

                payload = resp.json()
                for item in payload.get("data", []):
                    created_at = self._parse_timestamp(item.get("timestamp"))
                    if since and created_at <= since:
                        continue
                    comments.append(
                        Comment(
                            platform_comment_id=item.get("id", ""),
                            author_id=item.get("username", ""),
                            author_name=item.get("username", ""),
                            text=item.get("text", ""),
                            created_at=created_at,
                            parent_id=item.get("reply_to_id"),
                            raw=item,
                        )
                    )

                paging = payload.get("paging", {})
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{THREADS_API}/{credentials['threads_user_id']}/threads",
                params={
                    "media_type": "TEXT",
                    "text": text,
                    "reply_to_id": comment_id,
                    "access_token": credentials["access_token"],
                },
            )
            if resp.status_code != 200:
                return ReplyResult(success=False, error=resp.text)

            payload = resp.json()
            return ReplyResult(
                success=True,
                platform_comment_id=payload.get("id"),
            )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        results: list[AnalyticsData] = []
        token = credentials["access_token"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            if platform_post_id:
                resp = await client.get(
                    f"{THREADS_API}/{platform_post_id}/insights",
                    params={
                        "metric": "views,likes,replies,reposts,quotes",
                        "access_token": token,
                    },
                )
                if resp.status_code != 200:
                    return results

                metrics: dict[str, int] = {}
                for entry in resp.json().get("data", []):
                    name = entry.get("name", "")
                    value = entry.get("values", [{}])[0].get("value", 0)
                    metrics[name] = int(value) if isinstance(value, (int, float)) else 0

                views = metrics.get("views", 0)
                likes = metrics.get("likes", 0)
                comments = metrics.get("replies", 0)
                shares = metrics.get("reposts", 0) + metrics.get("quotes", 0)
                denominator = views if views > 0 else 1
                results.append(
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
                )
                return results

            resp = await client.get(
                f"{THREADS_API}/me",
                params={
                    "fields": "id,username,followers_count",
                    "access_token": token,
                },
            )
            if resp.status_code != 200:
                return results

            payload = resp.json()
            results.append(
                AnalyticsData(
                    platform=self.platform_name,
                    followers=int(payload.get("followers_count", 0)),
                    raw=payload,
                )
            )
        return results
