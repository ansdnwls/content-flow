"""Tistory adapter — Tistory Open API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

TISTORY_API = "https://www.tistory.com/apis"


class TistoryAdapter(PlatformAdapter):
    platform_name = "tistory"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        blog_name = credentials["blog_name"]

        title = options.get("title", "ContentFlow Post")
        category_id = options.get("category_id", "0")
        visibility = options.get("visibility", "3")  # 0:private 3:public
        tag = options.get("tag", "")

        # Build HTML content
        content_parts: list[str] = []
        for m in media:
            if m.media_type == "image":
                content_parts.append(f'<img src="{m.url}" />')
            elif m.media_type == "video":
                content_parts.append(
                    f'<iframe src="{m.url}" allowfullscreen></iframe>'
                )
        if text:
            content_parts.append(f"<p>{text}</p>")

        params: dict[str, Any] = {
            "access_token": access_token,
            "output": "json",
            "blogName": blog_name,
            "title": title,
            "content": "\n".join(content_parts),
            "visibility": visibility,
            "category": category_id,
            "tag": tag,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{TISTORY_API}/post/write", data=params)

            if resp.status_code != 200:
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            tistory_resp = data.get("tistory", {})

            if tistory_resp.get("status") != "200":
                return PublishResult(
                    success=False,
                    error=tistory_resp.get("error_message", "Unknown error"),
                    raw_response=data,
                )

            post_id = str(tistory_resp.get("postId", ""))
            url = tistory_resp.get("url")

            return PublishResult(
                success=True,
                platform_post_id=post_id,
                url=url,
                raw_response=data,
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        access_token = credentials["access_token"]
        blog_name = credentials["blog_name"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{TISTORY_API}/post/delete",
                data={
                    "access_token": access_token,
                    "blogName": blog_name,
                    "postId": platform_post_id,
                    "output": "json",
                },
            )
            if resp.status_code != 200:
                return False
            data = resp.json()
            return data.get("tistory", {}).get("status") == "200"

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{TISTORY_API}/blog/info",
                params={"access_token": access_token, "output": "json"},
            )
            if resp.status_code != 200:
                return False
            return resp.json().get("tistory", {}).get("status") == "200"
