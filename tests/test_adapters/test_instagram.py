"""Tests for Instagram adapter."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.instagram import InstagramAdapter

CREDS = {"access_token": "fake_token", "ig_user_id": "ig_001"}


@pytest.fixture
def adapter() -> InstagramAdapter:
    return InstagramAdapter()


class TestPublish:
    @respx.mock
    async def test_reel(self, adapter, video_media):
        respx.post("https://graph.facebook.com/v21.0/ig_001/media").mock(
            return_value=httpx.Response(200, json={"id": "container_001"})
        )
        respx.get("https://graph.facebook.com/v21.0/container_001").mock(
            return_value=httpx.Response(200, json={"status_code": "FINISHED"})
        )
        respx.post("https://graph.facebook.com/v21.0/ig_001/media_publish").mock(
            return_value=httpx.Response(200, json={"id": "ig_post_001"})
        )

        result = await adapter.publish("Reel caption", video_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "ig_post_001"

    @respx.mock
    async def test_single_image(self, adapter, image_media):
        respx.post("https://graph.facebook.com/v21.0/ig_001/media").mock(
            return_value=httpx.Response(200, json={"id": "container_img"})
        )
        respx.get("https://graph.facebook.com/v21.0/container_img").mock(
            return_value=httpx.Response(200, json={"status_code": "FINISHED"})
        )
        respx.post("https://graph.facebook.com/v21.0/ig_001/media_publish").mock(
            return_value=httpx.Response(200, json={"id": "ig_img_001"})
        )

        result = await adapter.publish("Image post", image_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "ig_img_001"

    @respx.mock
    async def test_carousel(self, adapter, multi_image_media):
        respx.post("https://graph.facebook.com/v21.0/ig_001/media").mock(
            side_effect=[
                httpx.Response(200, json={"id": "child_1"}),
                httpx.Response(200, json={"id": "child_2"}),
                httpx.Response(200, json={"id": "child_3"}),
                httpx.Response(200, json={"id": "carousel_container"}),
            ]
        )
        respx.get("https://graph.facebook.com/v21.0/carousel_container").mock(
            return_value=httpx.Response(200, json={"status_code": "FINISHED"})
        )
        respx.post("https://graph.facebook.com/v21.0/ig_001/media_publish").mock(
            return_value=httpx.Response(200, json={"id": "ig_carousel_001"})
        )

        result = await adapter.publish("Carousel", multi_image_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "ig_carousel_001"

    async def test_no_media(self, adapter):
        result = await adapter.publish("No media", [], {}, CREDS)

        assert not result.success
        assert "no supported media" in result.error.lower()

    @respx.mock
    async def test_container_fails(self, adapter, video_media):
        respx.post("https://graph.facebook.com/v21.0/ig_001/media").mock(
            return_value=httpx.Response(400, text="Invalid media")
        )

        result = await adapter.publish("Test", video_media, {}, CREDS)

        assert not result.success


class TestDelete:
    @respx.mock
    async def test_success(self, adapter):
        respx.delete("https://graph.facebook.com/v21.0/ig_post_001").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        assert await adapter.delete("ig_post_001", CREDS) is True

    @respx.mock
    async def test_failure(self, adapter):
        respx.delete("https://graph.facebook.com/v21.0/bad").mock(
            return_value=httpx.Response(404)
        )

        assert await adapter.delete("bad", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self, adapter):
        respx.get("https://graph.facebook.com/v21.0/me").mock(
            return_value=httpx.Response(200, json={"id": "ig_001"})
        )

        assert await adapter.validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self, adapter):
        respx.get("https://graph.facebook.com/v21.0/me").mock(
            return_value=httpx.Response(401)
        )

        assert await adapter.validate_credentials(CREDS) is False
