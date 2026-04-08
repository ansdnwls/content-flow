"""Tests for Medium adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.medium import MediumAdapter

API_BASE = "https://api.medium.com/v1"
CREDS = {"access_token": "test-token"}
USER_ID = "user-abc"


def adapter() -> MediumAdapter:
    return MediumAdapter()


def _mock_me():
    respx.get(f"{API_BASE}/me").mock(
        return_value=httpx.Response(200, json={
            "data": {"id": USER_ID, "username": "testuser"},
        })
    )


class TestPublish:
    @respx.mock
    async def test_markdown_draft(self):
        _mock_me()
        respx.post(f"{API_BASE}/users/{USER_ID}/posts").mock(
            return_value=httpx.Response(201, json={
                "data": {
                    "id": "post-1",
                    "url": "https://medium.com/@testuser/post-1",
                    "publishStatus": "draft",
                },
            })
        )
        result = await adapter().publish(
            "# Hello Medium\n\nThis is markdown content.",
            [],
            {
                "title": "Hello Medium",
                "content_format": "markdown",
                "publish_status": "draft",
                "tags": ["go", "programming"],
            },
            CREDS,
        )
        assert result.success
        assert result.platform_post_id == "post-1"
        assert "medium.com" in result.url

    @respx.mock
    async def test_html_public(self):
        _mock_me()
        respx.post(f"{API_BASE}/users/{USER_ID}/posts").mock(
            return_value=httpx.Response(201, json={
                "data": {
                    "id": "post-2",
                    "url": "https://medium.com/@testuser/post-2",
                    "publishStatus": "public",
                },
            })
        )
        result = await adapter().publish(
            "<h1>HTML Post</h1><p>Content</p>",
            [],
            {
                "title": "HTML Post",
                "content_format": "html",
                "publish_status": "public",
            },
            CREDS,
        )
        assert result.success

    @respx.mock
    async def test_with_canonical_url(self):
        _mock_me()
        respx.post(f"{API_BASE}/users/{USER_ID}/posts").mock(
            return_value=httpx.Response(201, json={
                "data": {"id": "post-3", "url": "https://medium.com/@testuser/post-3"},
            })
        )
        result = await adapter().publish(
            "Crosspost content",
            [],
            {
                "title": "Crosspost",
                "canonical_url": "https://myblog.com/original",
            },
            CREDS,
        )
        assert result.success

    @respx.mock
    async def test_user_id_failure(self):
        respx.get(f"{API_BASE}/me").mock(
            return_value=httpx.Response(401)
        )
        result = await adapter().publish("test", [], {"title": "T"}, CREDS)
        assert not result.success
        assert "user ID" in result.error

    @respx.mock
    async def test_post_api_error(self):
        _mock_me()
        respx.post(f"{API_BASE}/users/{USER_ID}/posts").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        result = await adapter().publish(
            "fail", [], {"title": "Fail"}, CREDS,
        )
        assert not result.success
        assert "Bad Request" in result.error


class TestDelete:
    async def test_not_supported(self):
        assert await adapter().delete("post-1", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        _mock_me()
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{API_BASE}/me").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
