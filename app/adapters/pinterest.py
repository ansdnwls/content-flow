"""Pinterest adapter — Pin creation via Pinterest API v5."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

API_BASE = "https://api.pinterest.com/v5"


class PinterestAdapter(PlatformAdapter):
    platform_name = "pinterest"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        board_id = credentials["board_id"]

        pin_data: dict[str, Any] = {"board_id": board_id}
        if text:
            pin_data["description"] = text

        title = options.get("title")
        if title:
            pin_data["title"] = title

        link = options.get("link")
        if link:
            pin_data["link"] = link

        alt_text = options.get("alt_text")

        if media:
            first = media[0]
            if first.media_type == "video":
                pin_data["media_source"] = {
                    "source_type": "video_id",
                    "cover_image_url": options.get("cover_image_url", first.url),
                    "media_id": options.get("media_id", ""),
                }
            else:
                pin_data["media_source"] = {
                    "source_type": "image_url",
                    "url": first.url,
                }
                if alt_text:
                    pin_data["alt_text"] = alt_text
        else:
            return PublishResult(success=False, error="Pinterest requires media")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{API_BASE}/pins",
                json=pin_data,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code not in (200, 201):
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            pin_id = data.get("id", "")
            return PublishResult(
                success=True,
                platform_post_id=pin_id,
                url=f"https://www.pinterest.com/pin/{pin_id}/",
                raw_response=data,
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{API_BASE}/pins/{platform_post_id}",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 204

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE}/user_account",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200
