"""Tests for WordPress adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.wordpress import WordPressAdapter

SITE = "https://example.com"
CREDS = {"access_token": "fake_token", "site_url": SITE}


def adapter() -> WordPressAdapter:
    return WordPressAdapter()


class TestPublish:
    @respx.mock
    async def test_text_post(self):
        respx.post(f"{SITE}/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(201, json={
                "id": 42, "link": "https://example.com/hello-world/"
            })
        )
        result = await adapter().publish(
            "<p>Hello WordPress</p>", [], {"title": "Hello World"}, CREDS
        )
        assert result.success
        assert result.platform_post_id == "42"
        assert "example.com" in result.url

    @respx.mock
    async def test_with_featured_image(self, image_media):
        # Mock image download
        respx.get(image_media[0].url).mock(
            return_value=httpx.Response(
                200, content=b"img_data",
                headers={"content-type": "image/jpeg"},
            )
        )
        # Mock media upload
        respx.post(f"{SITE}/wp-json/wp/v2/media").mock(
            return_value=httpx.Response(201, json={"id": 99})
        )
        # Mock post creation
        respx.post(f"{SITE}/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(201, json={
                "id": 43, "link": "https://example.com/img-post/"
            })
        )
        result = await adapter().publish(
            "Image post", image_media, {"title": "Img"}, CREDS
        )
        assert result.success

    @respx.mock
    async def test_api_error(self):
        respx.post(f"{SITE}/wp-json/wp/v2/posts").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        result = await adapter().publish("test", [], {}, CREDS)
        assert not result.success
        assert "Forbidden" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.delete(f"{SITE}/wp-json/wp/v2/posts/42").mock(
            return_value=httpx.Response(200, json={"deleted": True})
        )
        assert await adapter().delete("42", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.delete(f"{SITE}/wp-json/wp/v2/posts/999").mock(
            return_value=httpx.Response(404)
        )
        assert await adapter().delete("999", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{SITE}/wp-json/wp/v2/users/me").mock(
            return_value=httpx.Response(200, json={"id": 1})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{SITE}/wp-json/wp/v2/users/me").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
