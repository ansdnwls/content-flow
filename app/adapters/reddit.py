"""Reddit adapter — link/self/image posts via Reddit OAuth2 API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

API_BASE = "https://oauth.reddit.com"


class RedditAdapter(PlatformAdapter):
    platform_name = "reddit"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        subreddit = options.get("subreddit", credentials.get("subreddit", ""))
        title = options.get("title", "")

        if not subreddit:
            return PublishResult(success=False, error="subreddit is required")
        if not title:
            return PublishResult(success=False, error="title is required for Reddit")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ContentFlow/0.1",
        }
        data: dict[str, Any] = {
            "sr": subreddit,
            "title": title,
            "api_type": "json",
        }

        flair_id = options.get("flair_id")
        if flair_id:
            data["flair_id"] = flair_id
        nsfw = options.get("nsfw", False)
        if nsfw:
            data["nsfw"] = True
        spoiler = options.get("spoiler", False)
        if spoiler:
            data["spoiler"] = True

        if media:
            first = media[0]
            if first.media_type == "image":
                data["kind"] = "image"
                data["url"] = first.url
            else:
                data["kind"] = "link"
                data["url"] = first.url
        elif text:
            data["kind"] = "self"
            data["text"] = text
        else:
            data["kind"] = "self"
            data["text"] = ""

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{API_BASE}/api/submit",
                data=data,
                headers=headers,
            )
            if resp.status_code != 200:
                return PublishResult(success=False, error=resp.text)

            body = resp.json()
            json_data = body.get("json", {})
            errors = json_data.get("errors", [])
            if errors:
                return PublishResult(
                    success=False, error=str(errors), raw_response=body
                )

            result_data = json_data.get("data", {})
            post_url = result_data.get("url", "")
            post_id = result_data.get("id", result_data.get("name", ""))
            return PublishResult(
                success=True,
                platform_post_id=post_id,
                url=post_url,
                raw_response=body,
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "User-Agent": "ContentFlow/0.1",
        }
        fullname = platform_post_id
        if not fullname.startswith("t3_"):
            fullname = f"t3_{fullname}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{API_BASE}/api/del",
                data={"id": fullname},
                headers=headers,
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE}/api/v1/me",
                headers={
                    "Authorization": f"Bearer {credentials['access_token']}",
                    "User-Agent": "ContentFlow/0.1",
                },
            )
            return resp.status_code == 200
