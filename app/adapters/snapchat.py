"""Snapchat adapter — Snap Marketing API / Public Content Posting API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

SNAP_API = "https://adsapi.snapchat.com/v1"
PUBLIC_API = "https://kit.snapchat.com/v1"


class SnapchatAdapter(PlatformAdapter):
    platform_name = "snapchat"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        video = next((m for m in media if m.media_type == "video"), None)
        image = next((m for m in media if m.media_type == "image"), None)

        if not video and not image:
            return PublishResult(success=False, error="Snapchat requires media (video or image)")

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Create media
            media_item = video or image
            media_resp = await client.post(
                f"{SNAP_API}/media",
                headers=headers,
                json={
                    "media": [
                        {
                            "name": options.get("name", "ContentFlow upload"),
                            "type": "VIDEO" if media_item.media_type == "video" else "IMAGE",
                            "ad_account_id": credentials.get("ad_account_id", ""),
                        }
                    ]
                },
            )
            if media_resp.status_code not in (200, 201):
                return PublishResult(success=False, error=media_resp.text)

            media_data = media_resp.json()
            media_list = media_data.get("media", [])
            if not media_list:
                return PublishResult(success=False, error="No media object returned")

            snap_media_id = media_list[0].get("media", {}).get("id")
            upload_link = media_list[0].get("media", {}).get("upload_link")

            if not upload_link:
                return PublishResult(success=False, error="No upload link returned")

            # Step 2: Upload media binary
            dl_resp = await client.get(media_item.url)
            if dl_resp.status_code != 200:
                return PublishResult(success=False, error="Failed to download media")

            content_type = (
                "video/mp4" if media_item.media_type == "video" else "image/png"
            )
            upload_resp = await client.put(
                upload_link,
                content=dl_resp.content,
                headers={**headers, "Content-Type": content_type},
            )
            if upload_resp.status_code not in (200, 201):
                return PublishResult(success=False, error=upload_resp.text)

            # Step 3: Create creative / story
            creative_body = {
                "creatives": [
                    {
                        "ad_account_id": credentials.get("ad_account_id", ""),
                        "name": options.get("title", text or "ContentFlow post"),
                        "type": "SNAP_AD",
                        "top_snap_media_id": snap_media_id,
                        "headline": text or "",
                    }
                ]
            }
            ad_account_id = credentials.get("ad_account_id", "")
            creative_resp = await client.post(
                f"{SNAP_API}/adaccounts/{ad_account_id}/creatives",
                headers=headers,
                json=creative_body,
            )
            if creative_resp.status_code not in (200, 201):
                return PublishResult(success=False, error=creative_resp.text)

            creative_data = creative_resp.json()
            creatives = creative_data.get("creatives", [])
            creative_id = (
                creatives[0].get("creative", {}).get("id") if creatives else None
            )

            return PublishResult(
                success=True,
                platform_post_id=creative_id or snap_media_id,
                raw_response=creative_data,
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{SNAP_API}/creatives/{platform_post_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code in (200, 204)

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{SNAP_API}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code == 200
