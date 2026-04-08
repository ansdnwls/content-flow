"""LINE adapter — broadcast messages via LINE Messaging API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

API_BASE = "https://api.line.me/v2/bot"
NOTIFY_URL = "https://notify-api.line.me/api/notify"


class LINEAdapter(PlatformAdapter):
    platform_name = "line"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        # LINE Notify shortcut (simple notification to personal/group)
        if options.get("use_notify") and credentials.get("notify_token"):
            return await self._notify(text, media, credentials)

        channel_token = credentials["channel_access_token"]
        headers = {
            "Authorization": f"Bearer {channel_token}",
            "Content-Type": "application/json",
        }

        messages = self._build_messages(text, media, options)
        if not messages:
            return PublishResult(success=False, error="No content to send")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{API_BASE}/message/broadcast",
                json={"messages": messages},
                headers=headers,
            )
            if resp.status_code != 200:
                return PublishResult(
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp.text}",
                )

            request_id = resp.headers.get("X-Line-Request-Id", "")
            return PublishResult(
                success=True,
                platform_post_id=request_id,
                raw_response={"request_id": request_id},
            )

    def _build_messages(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        if text:
            messages.append({"type": "text", "text": text})

        for m in media:
            if m.media_type == "image":
                preview = options.get("preview_image_url", m.url)
                messages.append({
                    "type": "image",
                    "originalContentUrl": m.url,
                    "previewImageUrl": preview,
                })
            elif m.media_type == "video":
                preview = options.get("preview_image_url", "")
                messages.append({
                    "type": "video",
                    "originalContentUrl": m.url,
                    "previewImageUrl": preview,
                })

        return messages[:5]  # LINE allows max 5 messages per request

    async def _notify(
        self,
        text: str | None,
        media: list[MediaSpec],
        credentials: dict[str, str],
    ) -> PublishResult:
        token = credentials["notify_token"]
        headers = {"Authorization": f"Bearer {token}"}
        data: dict[str, Any] = {"message": text or ""}

        if media:
            first = media[0]
            if first.media_type == "image":
                data["imageThumbnail"] = first.url
                data["imageFullsize"] = first.url

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                NOTIFY_URL,
                data=data,
                headers=headers,
            )
            if resp.status_code != 200:
                return PublishResult(success=False, error=resp.text)

            return PublishResult(
                success=True,
                platform_post_id="notify",
                raw_response=resp.json(),
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        # LINE broadcast messages cannot be deleted via API
        return False

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        token = credentials.get("channel_access_token", "")
        if not token:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_BASE}/info",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code == 200
