"""Tests for YouTube adapter."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.adapters.youtube import YouTubeAdapter

CREDS = {"access_token": "fake_token"}


@pytest.fixture
def adapter() -> YouTubeAdapter:
    return YouTubeAdapter()


class TestPublish:
    @respx.mock
    async def test_success(self, adapter, video_media):
        respx.post("https://www.googleapis.com/upload/youtube/v3/videos").mock(
            return_value=httpx.Response(
                200, headers={"Location": "https://upload.example.com/yt"}
            )
        )
        respx.get("https://example.com/video.mp4").mock(
            return_value=httpx.Response(200, content=b"video_data")
        )
        respx.put("https://upload.example.com/yt").mock(
            return_value=httpx.Response(200, json={"id": "yt_001"})
        )

        result = await adapter.publish("Test", video_media, {"title": "My Vid"}, CREDS)

        assert result.success
        assert result.platform_post_id == "yt_001"
        assert "youtu.be" in result.url

    @respx.mock
    async def test_publish_at_forces_private_status(self, adapter, video_media):
        respx.post("https://www.googleapis.com/upload/youtube/v3/videos").mock(
            return_value=httpx.Response(
                200, headers={"Location": "https://upload.example.com/yt"}
            )
        )
        respx.get("https://example.com/video.mp4").mock(
            return_value=httpx.Response(200, content=b"video_data")
        )
        respx.put("https://upload.example.com/yt").mock(
            return_value=httpx.Response(200, json={"id": "yt_002"})
        )

        result = await adapter.publish(
            "Test",
            video_media,
            {"publish_at": "2026-04-08T10:00:00Z", "privacy": "public"},
            CREDS,
        )

        assert result.success
        request = respx.calls[0].request
        payload = json.loads(request.content)
        assert payload["status"]["privacyStatus"] == "private"
        assert payload["status"]["publishAt"] == "2026-04-08T10:00:00+00:00"

    @respx.mock
    async def test_no_video(self, adapter, image_media):
        result = await adapter.publish("Test", image_media, {}, CREDS)

        assert not result.success
        assert "no video" in result.error.lower()

    @respx.mock
    async def test_init_fails(self, adapter, video_media):
        respx.post("https://www.googleapis.com/upload/youtube/v3/videos").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )

        result = await adapter.publish("Test", video_media, {}, CREDS)

        assert not result.success

    @respx.mock
    async def test_no_upload_url(self, adapter, video_media):
        respx.post("https://www.googleapis.com/upload/youtube/v3/videos").mock(
            return_value=httpx.Response(200, headers={})
        )

        result = await adapter.publish("Test", video_media, {}, CREDS)

        assert not result.success
        assert "upload URL" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self, adapter):
        respx.delete("https://www.googleapis.com/youtube/v3/videos").mock(
            return_value=httpx.Response(204)
        )

        assert await adapter.delete("yt_001", CREDS) is True

    @respx.mock
    async def test_failure(self, adapter):
        respx.delete("https://www.googleapis.com/youtube/v3/videos").mock(
            return_value=httpx.Response(404)
        )

        assert await adapter.delete("bad", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self, adapter):
        respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        assert await adapter.validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self, adapter):
        respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
            return_value=httpx.Response(401)
        )

        assert await adapter.validate_credentials(CREDS) is False
