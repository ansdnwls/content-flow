"""YouTube adapter — Resumable upload via YouTube Data API v3."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult


class YouTubeAdapter(PlatformAdapter):
    platform_name = "youtube"

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

        snippet = {
            "title": options.get("title", text or "Untitled"),
            "description": options.get("description", ""),
            "tags": options.get("tags", []),
            "categoryId": options.get("category_id", "22"),
        }
        status_body = {"privacyStatus": options.get("privacy", "public")}

        async with httpx.AsyncClient() as client:
            # Step 1: Start resumable upload
            init_resp = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"snippet": snippet, "status": status_body},
            )
            if init_resp.status_code != 200:
                return PublishResult(success=False, error=init_resp.text)

            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                return PublishResult(success=False, error="No upload URL returned")

            # Step 2: Download media then upload
            media_resp = await client.get(video.url)
            upload_resp = await client.put(
                upload_url,
                content=media_resp.content,
                headers={"Content-Type": "video/*"},
            )

            if upload_resp.status_code in (200, 201):
                data = upload_resp.json()
                return PublishResult(
                    success=True,
                    platform_post_id=data["id"],
                    url=f"https://youtu.be/{data['id']}",
                    raw_response=data,
                )
            return PublishResult(success=False, error=upload_resp.text)

    async def delete(self, platform_post_id: str, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"id": platform_post_id},
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 204

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "id", "mine": "true"},
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200
