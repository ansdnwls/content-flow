"""Tests for Mastodon adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.mastodon import MastodonAdapter

INSTANCE = "https://mastodon.social"
CREDS = {"instance_url": INSTANCE, "access_token": "test-token"}


def adapter() -> MastodonAdapter:
    return MastodonAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self):
        respx.post(f"{INSTANCE}/api/v1/statuses").mock(
            return_value=httpx.Response(200, json={
                "id": "12345",
                "url": "https://mastodon.social/@user/12345",
            })
        )
        result = await adapter().publish("Hello Fediverse!", [], {}, CREDS)
        assert result.success
        assert result.platform_post_id == "12345"
        assert "mastodon.social" in result.url

    @respx.mock
    async def test_with_media(self, image_media):
        respx.get(image_media[0].url).mock(
            return_value=httpx.Response(
                200,
                content=b"fake-image",
                headers={"content-type": "image/png"},
            )
        )
        respx.post(f"{INSTANCE}/api/v2/media").mock(
            return_value=httpx.Response(200, json={"id": "media-1"})
        )
        respx.post(f"{INSTANCE}/api/v1/statuses").mock(
            return_value=httpx.Response(200, json={
                "id": "12346",
                "url": "https://mastodon.social/@user/12346",
            })
        )
        result = await adapter().publish(
            "With image", image_media, {"visibility": "unlisted"}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "12346"

    @respx.mock
    async def test_visibility_private(self):
        respx.post(f"{INSTANCE}/api/v1/statuses").mock(
            return_value=httpx.Response(200, json={
                "id": "12347", "url": None,
            })
        )
        result = await adapter().publish(
            "Private", [], {"visibility": "private"}, CREDS,
        )
        assert result.success

    @respx.mock
    async def test_api_error(self):
        respx.post(f"{INSTANCE}/api/v1/statuses").mock(
            return_value=httpx.Response(422, text="Unprocessable Entity")
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success
        assert "Unprocessable" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.delete(f"{INSTANCE}/api/v1/statuses/12345").mock(
            return_value=httpx.Response(200, json={})
        )
        assert await adapter().delete("12345", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.delete(f"{INSTANCE}/api/v1/statuses/99999").mock(
            return_value=httpx.Response(404)
        )
        assert await adapter().delete("99999", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{INSTANCE}/api/v1/accounts/verify_credentials").mock(
            return_value=httpx.Response(200, json={"id": "user-1"})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{INSTANCE}/api/v1/accounts/verify_credentials").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
