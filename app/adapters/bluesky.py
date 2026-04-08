"""Bluesky adapter — posting via AT Protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

API_BASE = "https://bsky.social/xrpc"


class BlueskyAdapter(PlatformAdapter):
    platform_name = "bluesky"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        did = credentials["did"]
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            embed = None
            if media:
                images = []
                for m in media:
                    if m.media_type != "image":
                        continue
                    blob = await self._upload_blob(client, headers, m.url)
                    if blob is None:
                        return PublishResult(
                            success=False, error=f"Blob upload failed for {m.url}"
                        )
                    alt = options.get("alt_text", "")
                    images.append({"alt": alt, "image": blob})

                if images:
                    embed = {
                        "$type": "app.bsky.embed.images",
                        "images": images,
                    }

            record: dict[str, Any] = {
                "$type": "app.bsky.feed.post",
                "text": text or "",
                "createdAt": datetime.now(UTC).isoformat(),
            }
            if embed:
                record["embed"] = embed

            langs = options.get("langs")
            if langs:
                record["langs"] = langs

            resp = await client.post(
                f"{API_BASE}/com.atproto.repo.createRecord",
                json={
                    "repo": did,
                    "collection": "app.bsky.feed.post",
                    "record": record,
                },
                headers=headers,
            )
            if resp.status_code != 200:
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            uri = data.get("uri", "")
            # Extract rkey for web URL
            rkey = uri.rsplit("/", 1)[-1] if "/" in uri else uri
            handle = options.get("handle", did)
            return PublishResult(
                success=True,
                platform_post_id=uri,
                url=f"https://bsky.app/profile/{handle}/post/{rkey}",
                raw_response=data,
            )

    async def _upload_blob(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        image_url: str,
    ) -> dict | None:
        """Download an image and upload it as a blob to Bluesky."""
        img_resp = await client.get(image_url)
        if img_resp.status_code != 200:
            return None

        content_type = img_resp.headers.get("content-type", "image/jpeg")
        upload_resp = await client.post(
            f"{API_BASE}/com.atproto.repo.uploadBlob",
            content=img_resp.content,
            headers={**headers, "Content-Type": content_type},
        )
        if upload_resp.status_code != 200:
            return None
        return upload_resp.json().get("blob")

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        rkey = platform_post_id.rsplit("/", 1)[-1] if "/" in platform_post_id else platform_post_id
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{API_BASE}/com.atproto.repo.deleteRecord",
                json={
                    "repo": credentials["did"],
                    "collection": "app.bsky.feed.post",
                    "rkey": rkey,
                },
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE}/com.atproto.server.getSession",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200
