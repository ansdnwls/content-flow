"""Tests for Google Business Profile adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.google_business import GoogleBusinessAdapter

LOCATION = "accounts/123/locations/456"
CREDS = {"access_token": "fake_token", "location_name": LOCATION}
API = "https://mybusiness.googleapis.com/v4"


def adapter() -> GoogleBusinessAdapter:
    return GoogleBusinessAdapter()


class TestPublish:
    @respx.mock
    async def test_text_post(self):
        respx.post(f"{API}/{LOCATION}/localPosts").mock(
            return_value=httpx.Response(200, json={
                "name": f"{LOCATION}/localPosts/post_001",
                "searchUrl": "https://search.google.com/local/posts?q=test",
            })
        )
        result = await adapter().publish("Check us out!", [], {}, CREDS)
        assert result.success
        assert "post_001" in result.platform_post_id
        assert "google.com" in result.url

    @respx.mock
    async def test_with_media(self, image_media):
        respx.post(f"{API}/{LOCATION}/localPosts").mock(
            return_value=httpx.Response(200, json={
                "name": f"{LOCATION}/localPosts/post_002",
            })
        )
        result = await adapter().publish("New photo!", image_media, {}, CREDS)
        assert result.success

    @respx.mock
    async def test_with_cta(self):
        respx.post(f"{API}/{LOCATION}/localPosts").mock(
            return_value=httpx.Response(200, json={
                "name": f"{LOCATION}/localPosts/post_003",
            })
        )
        result = await adapter().publish(
            "Visit us",
            [],
            {"action_type": "LEARN_MORE", "action_url": "https://example.com"},
            CREDS,
        )
        assert result.success

    @respx.mock
    async def test_api_error(self):
        respx.post(f"{API}/{LOCATION}/localPosts").mock(
            return_value=httpx.Response(403, text="Permission denied")
        )
        result = await adapter().publish("test", [], {}, CREDS)
        assert not result.success
        assert "Permission denied" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self):
        post_name = f"{LOCATION}/localPosts/post_001"
        respx.delete(f"{API}/{post_name}").mock(
            return_value=httpx.Response(204)
        )
        assert await adapter().delete(post_name, CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.delete(f"{API}/bad/path").mock(
            return_value=httpx.Response(404)
        )
        assert await adapter().delete("bad/path", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(
            f"https://mybusinessbusinessinformation.googleapis.com/v1/{LOCATION}"
        ).mock(return_value=httpx.Response(200, json={"name": LOCATION}))
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(
            f"https://mybusinessbusinessinformation.googleapis.com/v1/{LOCATION}"
        ).mock(return_value=httpx.Response(401))
        assert await adapter().validate_credentials(CREDS) is False
