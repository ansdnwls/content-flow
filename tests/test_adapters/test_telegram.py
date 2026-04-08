"""Tests for Telegram adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.telegram import TelegramAdapter

CREDS = {"bot_token": "123:ABCDEF", "chat_id": "@testchannel"}
BOT_BASE = "https://api.telegram.org/bot123:ABCDEF"


def adapter() -> TelegramAdapter:
    return TelegramAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self):
        respx.post(f"{BOT_BASE}/sendMessage").mock(
            return_value=httpx.Response(200, json={
                "ok": True,
                "result": {
                    "message_id": 42,
                    "chat": {"id": -1001234, "username": "testchannel"},
                },
            })
        )
        result = await adapter().publish("Hello Telegram!", [], {}, CREDS)
        assert result.success
        assert result.platform_post_id == "42"
        assert "t.me/testchannel/42" in result.url

    @respx.mock
    async def test_single_photo(self, image_media):
        respx.post(f"{BOT_BASE}/sendPhoto").mock(
            return_value=httpx.Response(200, json={
                "ok": True,
                "result": {"message_id": 43, "chat": {"id": -1001234}},
            })
        )
        result = await adapter().publish("Photo", image_media, {}, CREDS)
        assert result.success
        assert result.platform_post_id == "43"

    @respx.mock
    async def test_video(self, video_media):
        respx.post(f"{BOT_BASE}/sendVideo").mock(
            return_value=httpx.Response(200, json={
                "ok": True,
                "result": {"message_id": 44, "chat": {"id": -1001234}},
            })
        )
        result = await adapter().publish("Video", video_media, {}, CREDS)
        assert result.success

    @respx.mock
    async def test_media_group(self, multi_image_media):
        respx.post(f"{BOT_BASE}/sendMediaGroup").mock(
            return_value=httpx.Response(200, json={
                "ok": True,
                "result": [
                    {"message_id": 45, "chat": {"id": -1001234, "username": "testchannel"}},
                    {"message_id": 46, "chat": {"id": -1001234, "username": "testchannel"}},
                ],
            })
        )
        result = await adapter().publish("Group", multi_image_media, {}, CREDS)
        assert result.success
        assert result.platform_post_id == "45"

    @respx.mock
    async def test_api_error(self):
        respx.post(f"{BOT_BASE}/sendMessage").mock(
            return_value=httpx.Response(200, json={
                "ok": False, "description": "Bad Request: chat not found"
            })
        )
        result = await adapter().publish("test", [], {}, CREDS)
        assert not result.success
        assert "chat not found" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.post(f"{BOT_BASE}/deleteMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": True})
        )
        assert await adapter().delete("42", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.post(f"{BOT_BASE}/deleteMessage").mock(
            return_value=httpx.Response(200, json={"ok": False})
        )
        assert await adapter().delete("999", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{BOT_BASE}/getMe").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"id": 123}})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{BOT_BASE}/getMe").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
