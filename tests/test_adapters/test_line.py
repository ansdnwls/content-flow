"""Tests for LINE adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.line import LINEAdapter

CREDS = {"channel_access_token": "test-channel-token"}
BOT_BASE = "https://api.line.me/v2/bot"
NOTIFY_URL = "https://notify-api.line.me/api/notify"


def adapter() -> LINEAdapter:
    return LINEAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self):
        respx.post(f"{BOT_BASE}/message/broadcast").mock(
            return_value=httpx.Response(
                200,
                headers={"X-Line-Request-Id": "req-123"},
            )
        )
        result = await adapter().publish("Hello LINE!", [], {}, CREDS)
        assert result.success
        assert result.platform_post_id == "req-123"

    @respx.mock
    async def test_with_image(self, image_media):
        respx.post(f"{BOT_BASE}/message/broadcast").mock(
            return_value=httpx.Response(
                200,
                headers={"X-Line-Request-Id": "req-456"},
            )
        )
        result = await adapter().publish("Photo", image_media, {}, CREDS)
        assert result.success
        sent = respx.calls.last.request
        assert b"image" in sent.content

    @respx.mock
    async def test_with_video(self, video_media):
        respx.post(f"{BOT_BASE}/message/broadcast").mock(
            return_value=httpx.Response(
                200,
                headers={"X-Line-Request-Id": "req-789"},
            )
        )
        result = await adapter().publish("Video", video_media, {}, CREDS)
        assert result.success

    @respx.mock
    async def test_api_error(self):
        respx.post(f"{BOT_BASE}/message/broadcast").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success
        assert "400" in result.error

    @respx.mock
    async def test_notify_mode(self, image_media):
        notify_creds = {
            "channel_access_token": "tok",
            "notify_token": "notify-tok",
        }
        respx.post(NOTIFY_URL).mock(
            return_value=httpx.Response(200, json={"status": 200})
        )
        result = await adapter().publish(
            "Notify!", image_media, {"use_notify": True}, notify_creds,
        )
        assert result.success
        assert result.platform_post_id == "notify"

    async def test_empty_content(self):
        result = await adapter().publish(None, [], {}, CREDS)
        assert not result.success
        assert "No content" in result.error


class TestDelete:
    async def test_not_supported(self):
        assert await adapter().delete("req-123", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{BOT_BASE}/info").mock(
            return_value=httpx.Response(200, json={})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{BOT_BASE}/info").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
