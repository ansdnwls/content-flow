"""Kakao adapter — Kakao Story / KakaoTalk Channel posting via Kakao API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

KAKAO_API = "https://kapi.kakao.com"


class KakaoAdapter(PlatformAdapter):
    platform_name = "kakao"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Determine target: "story" (default) or "channel"
        target = options.get("target", "story")
        permission = options.get("permission", "A")  # A=all, F=friends, M=me

        async with httpx.AsyncClient(timeout=30.0) as client:
            if target == "channel":
                return await self._post_channel(client, headers, text, media, options)
            return await self._post_story(client, headers, text, media, permission)

    async def _post_story(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        text: str | None,
        media: list[MediaSpec],
        permission: str,
    ) -> PublishResult:
        # Upload images first if present
        image_urls: list[str] = []
        for m in media:
            if m.media_type == "image":
                upload_resp = await client.post(
                    f"{KAKAO_API}/v1/api/story/upload/multi",
                    headers=headers,
                    data={"image_url": m.url},
                )
                if upload_resp.status_code == 200:
                    for item in upload_resp.json():
                        image_urls.append(item.get("url", m.url))

        if image_urls:
            import json as json_mod

            body = {
                "image_url_list": json_mod.dumps(image_urls),
                "content": text or "",
                "permission": permission,
            }
            resp = await client.post(
                f"{KAKAO_API}/v1/api/story/post/photo",
                headers=headers,
                data=body,
            )
        else:
            resp = await client.post(
                f"{KAKAO_API}/v1/api/story/post/note",
                headers=headers,
                data={"content": text or "", "permission": permission},
            )

        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        story_id = data.get("id", "")
        return PublishResult(
            success=True,
            platform_post_id=story_id,
            url=data.get("url"),
            raw_response=data,
        )

    async def _post_channel(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
    ) -> PublishResult:
        # Kakao Channel message via Talk Channel API
        channel_id = options.get("channel_id", "")
        body: dict[str, Any] = {
            "channel_public_id": channel_id,
            "template_object": {
                "object_type": "text",
                "text": text or "",
                "link": {"web_url": options.get("link_url", "")},
            },
        }
        resp = await client.post(
            f"{KAKAO_API}/v1/api/talk/channel/message/send",
            headers=headers,
            json=body,
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        if data.get("result_code") != 0:
            return PublishResult(
                success=False,
                error=data.get("result_message", "Unknown error"),
                raw_response=data,
            )

        return PublishResult(
            success=True,
            platform_post_id=str(data.get("result_code", "")),
            raw_response=data,
        )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{KAKAO_API}/v1/api/story/delete/mystory",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"id": platform_post_id},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{KAKAO_API}/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code == 200
