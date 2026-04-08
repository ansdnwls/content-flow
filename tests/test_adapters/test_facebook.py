"""Tests for Facebook adapter."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.facebook import FacebookAdapter

CREDS = {"page_access_token": "fake_page_token", "page_id": "page_001"}


@pytest.fixture
def adapter() -> FacebookAdapter:
    return FacebookAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self, adapter):
        respx.post("https://graph.facebook.com/v19.0/page_001/feed").mock(
            return_value=httpx.Response(200, json={"id": "page_001_post_001"})
        )

        result = await adapter.publish("Hello Facebook", [], {}, CREDS)

        assert result.success
        assert result.platform_post_id == "page_001_post_001"

    @respx.mock
    async def test_with_link(self, adapter):
        respx.post("https://graph.facebook.com/v19.0/page_001/feed").mock(
            return_value=httpx.Response(200, json={"id": "page_001_post_002"})
        )

        result = await adapter.publish(
            "Check this out", [], {"link": "https://example.com"}, CREDS
        )

        assert result.success

    @respx.mock
    async def test_single_photo(self, adapter, image_media):
        respx.post("https://graph.facebook.com/v19.0/page_001/photos").mock(
            return_value=httpx.Response(
                200, json={"id": "photo_001", "post_id": "page_001_photo_001"}
            )
        )

        result = await adapter.publish("Photo post", image_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "page_001_photo_001"

    @respx.mock
    async def test_multi_photo(self, adapter, multi_image_media):
        # Upload unpublished photos
        respx.post("https://graph.facebook.com/v19.0/page_001/photos").mock(
            side_effect=[
                httpx.Response(200, json={"id": "ph1"}),
                httpx.Response(200, json={"id": "ph2"}),
                httpx.Response(200, json={"id": "ph3"}),
            ]
        )
        # Create post with attached media
        respx.post("https://graph.facebook.com/v19.0/page_001/feed").mock(
            return_value=httpx.Response(200, json={"id": "multi_post_001"})
        )

        result = await adapter.publish("Multi photo", multi_image_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "multi_post_001"

    @respx.mock
    async def test_video(self, adapter, video_media):
        respx.post("https://graph.facebook.com/v19.0/page_001/videos").mock(
            return_value=httpx.Response(200, json={"id": "vid_001"})
        )

        result = await adapter.publish("Video post", video_media, {"title": "My Video"}, CREDS)

        assert result.success
        assert result.platform_post_id == "vid_001"
        assert "facebook.com" in result.url

    @respx.mock
    async def test_api_error(self, adapter):
        respx.post("https://graph.facebook.com/v19.0/page_001/feed").mock(
            return_value=httpx.Response(400, text="Invalid token")
        )

        result = await adapter.publish("test", [], {}, CREDS)

        assert not result.success
        assert "Invalid token" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self, adapter):
        respx.delete("https://graph.facebook.com/v19.0/post_001").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        assert await adapter.delete("post_001", CREDS) is True

    @respx.mock
    async def test_failure(self, adapter):
        respx.delete("https://graph.facebook.com/v19.0/bad_id").mock(
            return_value=httpx.Response(404)
        )

        assert await adapter.delete("bad_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self, adapter):
        respx.get("https://graph.facebook.com/v19.0/me").mock(
            return_value=httpx.Response(200, json={"id": "page_001"})
        )

        assert await adapter.validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self, adapter):
        respx.get("https://graph.facebook.com/v19.0/me").mock(
            return_value=httpx.Response(401)
        )

        assert await adapter.validate_credentials(CREDS) is False
