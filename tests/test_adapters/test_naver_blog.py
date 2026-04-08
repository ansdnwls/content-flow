"""Tests for Naver Blog adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.naver_blog import BLOG_API, NAVER_API, NaverBlogAdapter

CREDS = {"access_token": "naver_tok_123"}


def adapter() -> NaverBlogAdapter:
    return NaverBlogAdapter()


class TestPublish:
    @respx.mock
    async def test_text_post_success(self):
        respx.post(BLOG_API).mock(
            return_value=httpx.Response(200, json={
                "logNo": "12345",
                "blogId": "testuser",
            })
        )
        result = await adapter().publish(
            "Hello Naver!", [], {"title": "Test Post"}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "12345"
        assert result.url == "https://blog.naver.com/testuser/12345"

    @respx.mock
    async def test_with_image(self, image_media):
        respx.post(BLOG_API).mock(
            return_value=httpx.Response(200, json={
                "logNo": "67890",
                "blogId": "imguser",
            })
        )
        result = await adapter().publish(
            "Image post", image_media, {"title": "Img"}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "67890"

    @respx.mock
    async def test_with_video(self, video_media):
        respx.post(BLOG_API).mock(
            return_value=httpx.Response(200, json={
                "logNo": "11111",
                "blogId": "viduser",
            })
        )
        result = await adapter().publish(
            "Video post", video_media, {}, CREDS,
        )
        assert result.success

    @respx.mock
    async def test_api_error(self):
        respx.post(BLOG_API).mock(
            return_value=httpx.Response(200, json={
                "error": "invalid_token",
                "error_description": "Token expired",
            })
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success
        assert "Token expired" in result.error

    @respx.mock
    async def test_http_error(self):
        respx.post(BLOG_API).mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success

    @respx.mock
    async def test_no_blog_id_returns_no_url(self):
        respx.post(BLOG_API).mock(
            return_value=httpx.Response(200, json={
                "logNo": "99999",
            })
        )
        result = await adapter().publish("text", [], {}, CREDS)
        assert result.success
        assert result.url is None


class TestDelete:
    async def test_always_returns_false(self):
        # Naver Blog API has no public delete endpoint
        assert await adapter().delete("12345", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{NAVER_API}/v1/nid/me").mock(
            return_value=httpx.Response(200, json={"response": {"id": "u1"}})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{NAVER_API}/v1/nid/me").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
