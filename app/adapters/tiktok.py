"""TikTok adapter — Content Posting API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

TIKTOK_API = "https://open.tiktokapis.com/v2"


class TikTokAdapter(PlatformAdapter):
    platform_name = "tiktok"

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

        async with httpx.AsyncClient() as client:
            # Step 1: Init upload
            init_resp = await client.post(
                f"{TIKTOK_API}/post/publish/video/init/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "post_info": {
                        "title": options.get("title", text or ""),
                        "privacy_level": options.get("privacy_level", "PUBLIC_TO_EVERYONE"),
                        "disable_comment": options.get("disable_comment", False),
                        "disable_duet": options.get("disable_duet", False),
                        "disable_stitch": options.get("disable_stitch", False),
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": video.url,
                    },
                },
            )

            if init_resp.status_code != 200:
                return PublishResult(success=False, error=init_resp.text)

            data = init_resp.json()
            publish_id = data.get("data", {}).get("publish_id")
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
