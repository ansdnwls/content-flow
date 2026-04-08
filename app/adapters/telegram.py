"""Telegram adapter — channel posting via Bot API."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

API_BASE = "https://api.telegram.org"


class TelegramAdapter(PlatformAdapter):
    platform_name = "telegram"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        bot_token = credentials["bot_token"]
        chat_id = credentials["chat_id"]
        base = f"{API_BASE}/bot{bot_token}"

        parse_mode = options.get("parse_mode", "HTML")
        disable_notification = options.get("disable_notification", False)

        async with httpx.AsyncClient(timeout=60.0) as client:
            if not media:
                return await self._send_message(
                    client, base, chat_id, text, parse_mode, disable_notification
                )

            first = media[0]
            if first.media_type == "video":
                return await self._send_video(
                    client, base, chat_id, first.url, text, parse_mode,
                    disable_notification,
                )
            if first.media_type == "image" and len(media) == 1:
                return await self._send_photo(
                    client, base, chat_id, first.url, text, parse_mode,
                    disable_notification,
                )
            # Multiple images → media group
            return await self._send_media_group(
                client, base, chat_id, media, text, disable_notification
            )

    async def _send_message(
        self, client, base, chat_id, text, parse_mode, disable_notification
    ) -> PublishResult:
        resp = await client.post(
            f"{base}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text or "",
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            },
        )
        return self._parse_response(resp)

    async def _send_photo(
        self, client, base, chat_id, photo_url, caption, parse_mode,
        disable_notification,
    ) -> PublishResult:
        resp = await client.post(
            f"{base}/sendPhoto",
            json={
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption or "",
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            },
        )
        return self._parse_response(resp)

    async def _send_video(
        self, client, base, chat_id, video_url, caption, parse_mode,
        disable_notification,
    ) -> PublishResult:
        resp = await client.post(
            f"{base}/sendVideo",
            json={
                "chat_id": chat_id,
                "video": video_url,
                "caption": caption or "",
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            },
        )
        return self._parse_response(resp)

    async def _send_media_group(
        self, client, base, chat_id, media_list, caption, disable_notification
    ) -> PublishResult:
        input_media = []
        for i, m in enumerate(media_list):
            item: dict[str, Any] = {
                "type": "photo" if m.media_type == "image" else "video",
                "media": m.url,
            }
            if i == 0 and caption:
                item["caption"] = caption
            input_media.append(item)

        resp = await client.post(
            f"{base}/sendMediaGroup",
            json={
                "chat_id": chat_id,
                "media": input_media,
                "disable_notification": disable_notification,
            },
        )
        return self._parse_response(resp)

    @staticmethod
    def _parse_response(resp: httpx.Response) -> PublishResult:
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        body = resp.json()
        if not body.get("ok"):
            return PublishResult(
                success=False,
                error=body.get("description", "Unknown error"),
                raw_response=body,
            )

        result = body.get("result", {})
        # result can be a list (media group) or dict (single message)
        if isinstance(result, list):
            msg = result[0] if result else {}
        else:
            msg = result

        message_id = str(msg.get("message_id", ""))
        chat = msg.get("chat", {})
        chat_username = chat.get("username")
        url = (
            f"https://t.me/{chat_username}/{message_id}"
            if chat_username
            else None
        )
        return PublishResult(
            success=True,
            platform_post_id=message_id,
            url=url,
            raw_response=body,
        )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        bot_token = credentials["bot_token"]
        chat_id = credentials["chat_id"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{API_BASE}/bot{bot_token}/deleteMessage",
                json={"chat_id": chat_id, "message_id": int(platform_post_id)},
            )
            if resp.status_code != 200:
                return False
            return resp.json().get("ok", False)

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        bot_token = credentials["bot_token"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}/bot{bot_token}/getMe")
            return resp.status_code == 200 and resp.json().get("ok", False)
