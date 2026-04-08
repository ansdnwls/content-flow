"""Medium adapter — article publishing via Medium API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

API_BASE = "https://api.medium.com/v1"


class MediumAdapter(PlatformAdapter):
    platform_name = "medium"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        token = credentials["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            user_id = await self._get_user_id(client, headers)
            if not user_id:
                return PublishResult(
                    success=False, error="Failed to retrieve Medium user ID",
                )

            content_format = options.get("content_format", "markdown")
            publish_status = options.get("publish_status", "draft")
            title = options.get("title", "")

            post_data: dict[str, Any] = {
                "title": title,
                "contentFormat": content_format,
                "content": text or "",
                "publishStatus": publish_status,
            }

            tags = options.get("tags")
            if tags:
                post_data["tags"] = tags[:5]  # Medium allows max 5 tags

            canonical_url = options.get("canonical_url")
            if canonical_url:
                post_data["canonicalUrl"] = canonical_url

            resp = await client.post(
                f"{API_BASE}/users/{user_id}/posts",
                json=post_data,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                return PublishResult(success=False, error=resp.text)

            data = resp.json().get("data", {})
            return PublishResult(
                success=True,
                platform_post_id=str(data.get("id", "")),
                url=data.get("url"),
                raw_response=data,
            )

    async def _get_user_id(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
    ) -> str | None:
        resp = await client.get(f"{API_BASE}/me", headers=headers)
        if resp.status_code != 200:
            return None
        return resp.json().get("data", {}).get("id")

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        # Medium API does not support post deletion
        return False

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        token = credentials.get("access_token", "")
        if not token:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE}/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code == 200
