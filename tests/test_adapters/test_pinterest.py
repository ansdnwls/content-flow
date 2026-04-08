"""Tests for Pinterest adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.pinterest import PinterestAdapter

CREDS = {"access_token": "fake_token", "board_id": "board_001"}


def adapter() -> PinterestAdapter:
    return PinterestAdapter()


class TestPublish:
    @respx.mock
    async def test_image_pin(self, image_media):
        respx.post("https://api.pinterest.com/v5/pins").mock(
            return_value=httpx.Response(201, json={"id": "pin_001"})
        )
        result = await adapter().publish("Nice pin", image_media, {"title": "My Pin"}, CREDS)
        assert result.success
        assert result.platform_post_id == "pin_001"
        assert "pinterest.com" in result.url

    @respx.mock
    async def test_no_media_fails(self):
        result = await adapter().publish("Text only", [], {}, CREDS)
        assert not result.success
        assert "requires media" in result.error

    @respx.mock
    async def test_api_error(self, image_media):
        respx.post("https://api.pinterest.com/v5/pins").mock(
            return_value=httpx.Response(400, text="Invalid board")
        )
        result = await adapter().publish("test", image_media, {}, CREDS)
        assert not result.success
        assert "Invalid board" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.delete("https://api.pinterest.com/v5/pins/pin_001").mock(
            return_value=httpx.Response(204)
        )
        assert await adapter().delete("pin_001", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.delete("https://api.pinterest.com/v5/pins/bad_id").mock(
            return_value=httpx.Response(404)
        )
        assert await adapter().delete("bad_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get("https://api.pinterest.com/v5/user_account").mock(
            return_value=httpx.Response(200, json={"username": "test"})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get("https://api.pinterest.com/v5/user_account").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
