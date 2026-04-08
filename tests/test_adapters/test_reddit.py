"""Tests for Reddit adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.reddit import RedditAdapter

CREDS = {"access_token": "fake_token", "subreddit": "testsubreddit"}


def adapter() -> RedditAdapter:
    return RedditAdapter()


class TestPublish:
    @respx.mock
    async def test_self_post(self):
        respx.post("https://oauth.reddit.com/api/submit").mock(
            return_value=httpx.Response(200, json={
                "json": {
                    "errors": [],
                    "data": {"id": "abc123", "url": "https://reddit.com/r/test/abc123"},
                }
            })
        )
        result = await adapter().publish(
            "Hello Reddit", [], {"subreddit": "test", "title": "My Post"}, CREDS
        )
        assert result.success
        assert result.platform_post_id == "abc123"

    @respx.mock
    async def test_image_post(self, image_media):
        respx.post("https://oauth.reddit.com/api/submit").mock(
            return_value=httpx.Response(200, json={
                "json": {"errors": [], "data": {"id": "img_001", "url": "https://reddit.com/r/test/img_001"}}
            })
        )
        result = await adapter().publish(
            "Image post", image_media, {"subreddit": "test", "title": "Photo"}, CREDS
        )
        assert result.success

    def test_missing_subreddit(self):
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            adapter().publish("text", [], {"title": "T"}, {"access_token": "t"})
        )
        assert not result.success
        assert "subreddit" in result.error

    def test_missing_title(self):
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            adapter().publish("text", [], {"subreddit": "s"}, CREDS)
        )
        assert not result.success
        assert "title" in result.error

    @respx.mock
    async def test_api_errors(self):
        respx.post("https://oauth.reddit.com/api/submit").mock(
            return_value=httpx.Response(200, json={
                "json": {"errors": [["SUBREDDIT_NOEXIST", "invalid subreddit"]], "data": {}}
            })
        )
        result = await adapter().publish(
            "test", [], {"subreddit": "bad", "title": "T"}, CREDS
        )
        assert not result.success


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.post("https://oauth.reddit.com/api/del").mock(
            return_value=httpx.Response(200)
        )
        assert await adapter().delete("abc123", CREDS) is True

    @respx.mock
    async def test_with_prefix(self):
        respx.post("https://oauth.reddit.com/api/del").mock(
            return_value=httpx.Response(200)
        )
        assert await adapter().delete("t3_abc123", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.post("https://oauth.reddit.com/api/del").mock(
            return_value=httpx.Response(403)
        )
        assert await adapter().delete("abc123", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get("https://oauth.reddit.com/api/v1/me").mock(
            return_value=httpx.Response(200, json={"name": "testuser"})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get("https://oauth.reddit.com/api/v1/me").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
