"""Tests for Tistory adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.tistory import TISTORY_API, TistoryAdapter

CREDS = {"access_token": "tistory_tok_123", "blog_name": "myblog"}


def adapter() -> TistoryAdapter:
    return TistoryAdapter()


class TestPublish:
    @respx.mock
    async def test_text_post_success(self):
        respx.post(f"{TISTORY_API}/post/write").mock(
            return_value=httpx.Response(200, json={
                "tistory": {
                    "status": "200",
                    "postId": "42",
                    "url": "https://myblog.tistory.com/42",
                }
            })
        )
        result = await adapter().publish(
            "Hello Tistory!", [], {"title": "Test"}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "42"
        assert result.url == "https://myblog.tistory.com/42"

    @respx.mock
    async def test_with_image(self, image_media):
        respx.post(f"{TISTORY_API}/post/write").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "200", "postId": "43", "url": "https://myblog.tistory.com/43"}
            })
        )
        result = await adapter().publish(
            "Image post", image_media, {"title": "Img"}, CREDS,
        )
        assert result.success

    @respx.mock
    async def test_with_video(self, video_media):
        respx.post(f"{TISTORY_API}/post/write").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "200", "postId": "44", "url": "https://myblog.tistory.com/44"}
            })
        )
        result = await adapter().publish(
            "Video post", video_media, {}, CREDS,
        )
        assert result.success

    @respx.mock
    async def test_api_error_status(self):
        respx.post(f"{TISTORY_API}/post/write").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "403", "error_message": "Forbidden"}
            })
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success
        assert "Forbidden" in result.error

    @respx.mock
    async def test_http_error(self):
        respx.post(f"{TISTORY_API}/post/write").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success

    @respx.mock
    async def test_with_options(self):
        respx.post(f"{TISTORY_API}/post/write").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "200", "postId": "45", "url": "https://myblog.tistory.com/45"}
            })
        )
        result = await adapter().publish(
            "Options post", [], {
                "title": "Custom",
                "category_id": "10",
                "visibility": "0",
                "tag": "test,blog",
            }, CREDS,
        )
        assert result.success


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.post(f"{TISTORY_API}/post/delete").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "200"}
            })
        )
        assert await adapter().delete("42", CREDS) is True

    @respx.mock
    async def test_failure_http(self):
        respx.post(f"{TISTORY_API}/post/delete").mock(
            return_value=httpx.Response(500, text="Error")
        )
        assert await adapter().delete("42", CREDS) is False

    @respx.mock
    async def test_failure_status(self):
        respx.post(f"{TISTORY_API}/post/delete").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "403"}
            })
        )
        assert await adapter().delete("42", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{TISTORY_API}/blog/info").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "200", "item": {"blogs": []}}
            })
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid_http(self):
        respx.get(f"{TISTORY_API}/blog/info").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False

    @respx.mock
    async def test_invalid_status(self):
        respx.get(f"{TISTORY_API}/blog/info").mock(
            return_value=httpx.Response(200, json={
                "tistory": {"status": "403"}
            })
        )
        assert await adapter().validate_credentials(CREDS) is False
