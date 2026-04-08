"""Tests for Bluesky adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.bluesky import BlueskyAdapter

CREDS = {"access_token": "fake_token", "did": "did:plc:user123"}


def adapter() -> BlueskyAdapter:
    return BlueskyAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self):
        respx.post("https://bsky.social/xrpc/com.atproto.repo.createRecord").mock(
            return_value=httpx.Response(200, json={
                "uri": "at://did:plc:user123/app.bsky.feed.post/3k2abc",
                "cid": "bafyrei123",
            })
        )
        result = await adapter().publish(
            "Hello Bluesky!", [], {"handle": "user.bsky.social"}, CREDS
        )
        assert result.success
        assert "3k2abc" in result.url
        assert "bsky.app" in result.url

    @respx.mock
    async def test_with_image(self, image_media):
        # Mock image download
        respx.get(image_media[0].url).mock(
            return_value=httpx.Response(
                200, content=b"fake_image_data",
                headers={"content-type": "image/jpeg"},
            )
        )
        # Mock blob upload
        respx.post("https://bsky.social/xrpc/com.atproto.repo.uploadBlob").mock(
            return_value=httpx.Response(200, json={
                "blob": {"ref": {"$link": "blobref"}, "mimeType": "image/jpeg"},
            })
        )
        # Mock post creation
        respx.post("https://bsky.social/xrpc/com.atproto.repo.createRecord").mock(
            return_value=httpx.Response(200, json={"uri": "at://did:plc:user123/app.bsky.feed.post/img001"})
        )
        result = await adapter().publish("Image post", image_media, {}, CREDS)
        assert result.success

    @respx.mock
    async def test_api_error(self):
        respx.post("https://bsky.social/xrpc/com.atproto.repo.createRecord").mock(
            return_value=httpx.Response(400, text="InvalidRequest")
        )
        result = await adapter().publish("test", [], {}, CREDS)
        assert not result.success
        assert "InvalidRequest" in result.error

    @respx.mock
    async def test_blob_upload_failure(self, image_media):
        respx.get(image_media[0].url).mock(
            return_value=httpx.Response(404)
        )
        result = await adapter().publish("test", image_media, {}, CREDS)
        assert not result.success
        assert "Blob upload failed" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.post("https://bsky.social/xrpc/com.atproto.repo.deleteRecord").mock(
            return_value=httpx.Response(200)
        )
        assert await adapter().delete(
            "at://did:plc:user123/app.bsky.feed.post/3k2abc", CREDS
        ) is True

    @respx.mock
    async def test_failure(self):
        respx.post("https://bsky.social/xrpc/com.atproto.repo.deleteRecord").mock(
            return_value=httpx.Response(400)
        )
        assert await adapter().delete("bad_uri", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get("https://bsky.social/xrpc/com.atproto.server.getSession").mock(
            return_value=httpx.Response(200, json={"did": "did:plc:user123"})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get("https://bsky.social/xrpc/com.atproto.server.getSession").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
