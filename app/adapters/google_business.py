"""Google Business Profile adapter — local posts via Business Profile API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

API_BASE = "https://mybusiness.googleapis.com/v4"


class GoogleBusinessAdapter(PlatformAdapter):
    platform_name = "google_business"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        location_name = credentials["location_name"]  # e.g. accounts/123/locations/456
        headers = {"Authorization": f"Bearer {access_token}"}

        post_body: dict[str, Any] = {
            "languageCode": options.get("language_code", "en"),
            "topicType": options.get("topic_type", "STANDARD"),
        }

        if text:
            post_body["summary"] = text

        # Call-to-action button
        action_type = options.get("action_type")
        action_url = options.get("action_url")
        if action_type and action_url:
            post_body["callToAction"] = {
                "actionType": action_type,
                "url": action_url,
            }

        # Media attachment
        if media:
            media_items = []
            for m in media:
                media_format = "VIDEO" if m.media_type == "video" else "PHOTO"
                media_items.append({
                    "mediaFormat": media_format,
                    "sourceUrl": m.url,
                })
            post_body["media"] = media_items

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{API_BASE}/{location_name}/localPosts",
                json=post_body,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            post_name = data.get("name", "")
            search_url = data.get("searchUrl", "")
            return PublishResult(
                success=True,
                platform_post_id=post_name,
                url=search_url or None,
                raw_response=data,
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{API_BASE}/{platform_post_id}",
                headers={
                    "Authorization": f"Bearer {credentials['access_token']}"
                },
            )
            return resp.status_code in (200, 204)

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://mybusinessbusinessinformation.googleapis.com/v1/"
                f"{credentials['location_name']}",
                headers={
                    "Authorization": f"Bearer {credentials['access_token']}"
                },
            )
            return resp.status_code == 200
