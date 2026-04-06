"""Instagram adapter — Reels + Carousel via Graph API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

GRAPH_API = "https://graph.facebook.com/v19.0"


class InstagramAdapter(PlatformAdapter):
    platform_name = "instagram"

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
