"""Tests for TikTok adapter."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.tiktok import TikTokAdapter

CREDS = {"access_token": "fake_token"}


@pytest.fixture
def adapter() -> TikTokAdapter:
    return TikTokAdapter()


class TestPublish:
    @respx.mock
    async def test_success(self, adapter, video_media):
        respx.post("https://open.tiktokapis.com/v2/post/publish/video/init/").mock(
            return_value=httpx.Response(
                200, json={"data": {"publish_id": "tt_pub_001"}}
            )
        )

        result = await adapter.publish("TikTok vid", video_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "tt_pub_001"

    @respx.mock
    async def test_no_video(self, adapter, image_media):
        result = await adapter.publish("Test", image_media, {}, CREDS)

        assert not result.success
        assert "no video" in result.error.lower()

    @respx.mock
    async def test_api_error(self, adapter, video_media):
        respx.post("https://open.tiktokapis.com/v2/post/publish/video/init/").mock(
            return_value=httpx.Response(400, text="Bad request")
        )

        result = await adapter.publish("Test", video_media, {}, CREDS)

        assert not result.success

    @respx.mock
    async def test_with_options(self, adapter, video_media):
        respx.post("https://open.tiktokapis.com/v2/post/publish/video/init/").mock(
            return_value=httpx.Response(
                200, json={"data": {"publish_id": "tt_pub_002"}}
            )
        )

        result = await adapter.publish(
            "Test",
            video_media,
            {"privacy_level": "SELF_ONLY", "disable_duet": True},
            CREDS,
        )

        assert result.success

    async def test_invalid_privacy_level(self, adapter, video_media):
        result = await adapter.publish(
            "Test",
            video_media,
            {"privacy_level": "FRIENDS_ONLY"},
            CREDS,
        )

        assert not result.success
        assert "privacy_level" in result.error


class TestDelete:
    async def test_returns_false(self, adapter):
        """TikTok Content Posting API does not support deletion."""
        assert await adapter.delete("any_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self, adapter):
        respx.get("https://open.tiktokapis.com/v2/user/info/").mock(
            return_value=httpx.Response(200, json={"data": {"user": {}}})
        )

        assert await adapter.validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self, adapter):
        respx.get("https://open.tiktokapis.com/v2/user/info/").mock(
            return_value=httpx.Response(401)
        )

        assert await adapter.validate_credentials(CREDS) is False
