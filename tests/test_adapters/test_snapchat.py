"""Tests for Snapchat adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.snapchat import SNAP_API, SnapchatAdapter

CREDS = {"access_token": "snap_tok_123", "ad_account_id": "ad_acc_456"}


def adapter() -> SnapchatAdapter:
    return SnapchatAdapter()


class TestPublish:
    @respx.mock
    async def test_video_publish_success(self, video_media):
        # Step 1: Create media
        respx.post(f"{SNAP_API}/media").mock(
            return_value=httpx.Response(200, json={
                "media": [
                    {
                        "media": {
                            "id": "media_abc",
                            "upload_link": "https://snap-upload.example.com/upload",
                        }
                    }
                ]
            })
        )
        # Step 2: Download + upload media
        respx.get("https://example.com/video.mp4").mock(
            return_value=httpx.Response(200, content=b"fakevideo")
        )
        respx.put("https://snap-upload.example.com/upload").mock(
            return_value=httpx.Response(200)
        )
        # Step 3: Create creative
        respx.post(f"{SNAP_API}/adaccounts/ad_acc_456/creatives").mock(
            return_value=httpx.Response(200, json={
                "creatives": [
                    {"creative": {"id": "creative_xyz"}}
                ]
            })
        )

        result = await adapter().publish("Snap post", video_media, {}, CREDS)
        assert result.success
        assert result.platform_post_id == "creative_xyz"

    @respx.mock
    async def test_image_publish_success(self, image_media):
        respx.post(f"{SNAP_API}/media").mock(
            return_value=httpx.Response(200, json={
                "media": [
                    {
                        "media": {
                            "id": "media_img",
                            "upload_link": "https://snap-upload.example.com/upload_img",
                        }
                    }
                ]
            })
        )
        respx.get("https://example.com/image.jpg").mock(
            return_value=httpx.Response(200, content=b"fakeimage")
        )
        respx.put("https://snap-upload.example.com/upload_img").mock(
            return_value=httpx.Response(200)
        )
        respx.post(f"{SNAP_API}/adaccounts/ad_acc_456/creatives").mock(
            return_value=httpx.Response(200, json={
                "creatives": [{"creative": {"id": "creative_img"}}]
            })
        )

        result = await adapter().publish("Image snap", image_media, {}, CREDS)
        assert result.success
        assert result.platform_post_id == "creative_img"

    async def test_no_media_fails(self):
        result = await adapter().publish("text only", [], {}, CREDS)
        assert not result.success
        assert "requires media" in result.error

    @respx.mock
    async def test_media_create_fails(self, video_media):
        respx.post(f"{SNAP_API}/media").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        result = await adapter().publish("Snap", video_media, {}, CREDS)
        assert not result.success

    @respx.mock
    async def test_upload_fails(self, video_media):
        respx.post(f"{SNAP_API}/media").mock(
            return_value=httpx.Response(200, json={
                "media": [
                    {
                        "media": {
                            "id": "media_abc",
                            "upload_link": "https://snap-upload.example.com/upload",
                        }
                    }
                ]
            })
        )
        respx.get("https://example.com/video.mp4").mock(
            return_value=httpx.Response(200, content=b"fakevideo")
        )
        respx.put("https://snap-upload.example.com/upload").mock(
            return_value=httpx.Response(500, text="Upload error")
        )
        result = await adapter().publish("Snap", video_media, {}, CREDS)
        assert not result.success


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.delete(f"{SNAP_API}/creatives/creative_xyz").mock(
            return_value=httpx.Response(200)
        )
        assert await adapter().delete("creative_xyz", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.delete(f"{SNAP_API}/creatives/bad_id").mock(
            return_value=httpx.Response(404)
        )
        assert await adapter().delete("bad_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{SNAP_API}/me").mock(
            return_value=httpx.Response(200, json={"me": {"id": "user123"}})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{SNAP_API}/me").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
