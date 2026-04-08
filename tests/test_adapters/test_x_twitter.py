"""Tests for X (Twitter) adapter."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.adapters.x_twitter import XTwitterAdapter

CREDS = {"access_token": "fake_token"}


@pytest.fixture
def adapter() -> XTwitterAdapter:
    return XTwitterAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self, adapter):
        respx.post("https://api.x.com/2/tweets").mock(
            return_value=httpx.Response(
                201, json={"data": {"id": "tweet_001", "text": "hello"}}
            )
        )

        result = await adapter.publish("hello", [], {}, CREDS)

        assert result.success
        assert result.platform_post_id == "tweet_001"
        assert "x.com" in result.url

    @respx.mock
    async def test_with_video(self, adapter, video_media):
        respx.get("https://example.com/video.mp4").mock(
            return_value=httpx.Response(200, content=b"fake_video_bytes")
        )
        respx.post("https://api.x.com/2/media/upload/initialize").mock(
            return_value=httpx.Response(200, json={"data": {"id": "media_001"}})
        )
        respx.post("https://api.x.com/2/media/upload/media_001/append").mock(
            return_value=httpx.Response(200, json={"data": {"expires_at": 123}})
        )
        respx.post("https://api.x.com/2/media/upload/media_001/finalize").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"processing_info": {"state": "succeeded"}}},
            )
        )
        respx.post("https://api.x.com/2/tweets").mock(
            return_value=httpx.Response(201, json={"data": {"id": "tweet_002"}})
        )

        result = await adapter.publish("video post", video_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "tweet_002"

    @respx.mock
    async def test_api_error(self, adapter):
        respx.post("https://api.x.com/2/tweets").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )

        result = await adapter.publish("test", [], {}, CREDS)

        assert not result.success
        assert "Forbidden" in result.error

    @respx.mock
    async def test_media_upload_fails(self, adapter, video_media):
        respx.get("https://example.com/video.mp4").mock(
            return_value=httpx.Response(200, content=b"data")
        )
        respx.post("https://api.x.com/2/media/upload/initialize").mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        result = await adapter.publish("test", video_media, {}, CREDS)

        assert not result.success
        assert "upload failed" in result.error.lower()

    async def test_rejects_text_over_280_chars(self, adapter):
        result = await adapter.publish("x" * 281, [], {}, CREDS)

        assert not result.success
        assert "280" in result.error

    @respx.mock
    async def test_with_reply_settings(self, adapter):
        respx.post("https://api.x.com/2/tweets").mock(
            return_value=httpx.Response(201, json={"data": {"id": "tweet_003"}})
        )

        result = await adapter.publish(
            "reply test", [], {"reply_settings": "mentionedUsers"}, CREDS
        )

        assert result.success
        sent = respx.calls.last.request
        body = json.loads(sent.content)
        assert body["reply_settings"] == "mentionedUsers"


class TestDelete:
    @respx.mock
    async def test_success(self, adapter):
        respx.delete("https://api.x.com/2/tweets/tweet_001").mock(
            return_value=httpx.Response(200, json={"data": {"deleted": True}})
        )

        assert await adapter.delete("tweet_001", CREDS) is True

    @respx.mock
    async def test_not_found(self, adapter):
        respx.delete("https://api.x.com/2/tweets/bad_id").mock(
            return_value=httpx.Response(404)
        )

        assert await adapter.delete("bad_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self, adapter):
        respx.get("https://api.x.com/2/users/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": "u1"}})
        )

        assert await adapter.validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self, adapter):
        respx.get("https://api.x.com/2/users/me").mock(
            return_value=httpx.Response(401)
        )

        assert await adapter.validate_credentials(CREDS) is False
