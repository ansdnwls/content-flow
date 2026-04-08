"""WordPress adapter — post creation via REST API v2."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult


class WordPressAdapter(PlatformAdapter):
    platform_name = "wordpress"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        base_url = credentials["site_url"].rstrip("/")
        token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        post_data: dict[str, Any] = {
            "status": options.get("status", "publish"),
            "content": text or "",
        }

        title = options.get("title")
        if title:
            post_data["title"] = title

        excerpt = options.get("excerpt")
        if excerpt:
            post_data["excerpt"] = excerpt

        categories = options.get("categories")
        if categories:
            post_data["categories"] = categories

        tags = options.get("tags")
        if tags:
            post_data["tags"] = tags

        slug = options.get("slug")
        if slug:
            post_data["slug"] = slug

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Upload featured image if provided
            if media:
                first = media[0]
                media_id = await self._upload_media(
                    client, base_url, headers, first.url
                )
                if media_id:
                    post_data["featured_media"] = media_id

            resp = await client.post(
                f"{base_url}/wp-json/wp/v2/posts",
                json=post_data,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            post_id = str(data.get("id", ""))
            post_link = data.get("link", "")
            return PublishResult(
                success=True,
                platform_post_id=post_id,
                url=post_link,
                raw_response=data,
            )

    async def _upload_media(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        headers: dict[str, str],
        media_url: str,
    ) -> int | None:
        """Download media and upload to WordPress media library."""
        dl_resp = await client.get(media_url)
        if dl_resp.status_code != 200:
            return None

        content_type = dl_resp.headers.get("content-type", "image/jpeg")
        filename = media_url.rsplit("/", 1)[-1] or "upload"

        upload_resp = await client.post(
            f"{base_url}/wp-json/wp/v2/media",
            content=dl_resp.content,
            headers={
                **headers,
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
        if upload_resp.status_code not in (200, 201):
            return None
        return upload_resp.json().get("id")

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        base_url = credentials["site_url"].rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{base_url}/wp-json/wp/v2/posts/{platform_post_id}",
                params={"force": "true"},
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        base_url = credentials["site_url"].rstrip("/")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base_url}/wp-json/wp/v2/users/me",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200
