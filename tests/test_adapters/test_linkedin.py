"""Tests for LinkedIn adapter."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.linkedin import LinkedInAdapter

CREDS = {
    "access_token": "fake_token",
    "author_urn": "urn:li:person:abc123",
}


@pytest.fixture
def adapter() -> LinkedInAdapter:
    return LinkedInAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self, adapter):
        respx.post("https://api.linkedin.com/rest/posts").mock(
            return_value=httpx.Response(
                201,
                headers={"x-restli-id": "urn:li:share:12345"},
                json={},
            )
        )

        result = await adapter.publish("Hello LinkedIn", [], {}, CREDS)

        assert result.success
        assert result.platform_post_id == "urn:li:share:12345"
        assert "linkedin.com" in result.url

    @respx.mock
    async def test_with_image(self, adapter, image_media):
        # Mock image upload registration
        respx.post(
            "https://api.linkedin.com/rest/images", params__contains={"action": "initializeUpload"}
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": {
                        "uploadUrl": "https://upload.linkedin.com/img/xxx",
                        "image": "urn:li:image:abc",
                    }
                },
            )
        )
        # Mock image download
        respx.get("https://example.com/image.jpg").mock(
            return_value=httpx.Response(200, content=b"fake_img")
        )
        # Mock binary upload
        respx.put("https://upload.linkedin.com/img/xxx").mock(
            return_value=httpx.Response(201)
        )
        # Mock post creation
        respx.post("https://api.linkedin.com/rest/posts").mock(
            return_value=httpx.Response(
                201,
                headers={"x-restli-id": "urn:li:share:67890"},
                json={},
            )
        )

        result = await adapter.publish("Image post", image_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "urn:li:share:67890"

    @respx.mock
    async def test_with_video(self, adapter, video_media):
        respx.post(
            "https://api.linkedin.com/rest/videos", params__contains={"action": "initializeUpload"}
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": {
                        "video": "urn:li:video:abc",
                        "uploadToken": "upload-token",
                        "uploadInstructions": [
                            {
                                "uploadUrl": "https://upload.linkedin.com/video/part-1",
                                "firstByte": 0,
                                "lastByte": 15,
                            }
                        ],
                    }
                },
            )
        )
        respx.get("https://example.com/video.mp4").mock(
            return_value=httpx.Response(200, content=b"0123456789abcdef")
        )
        respx.put("https://upload.linkedin.com/video/part-1").mock(
            return_value=httpx.Response(201, headers={"ETag": '"part-etag-1"'})
        )
        respx.post(
            "https://api.linkedin.com/rest/videos", params__contains={"action": "finalizeUpload"}
        ).mock(return_value=httpx.Response(201, json={}))
        respx.post("https://api.linkedin.com/rest/posts").mock(
            return_value=httpx.Response(
                201,
                headers={"x-restli-id": "urn:li:share:video-post"},
                json={},
            )
        )

        result = await adapter.publish("Video post", video_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "urn:li:share:video-post"

    @respx.mock
    async def test_missing_author(self, adapter):
        creds = {"access_token": "fake_token"}  # no author_urn

        result = await adapter.publish("Test", [], {}, creds)

        assert not result.success
        assert "author" in result.error.lower()

    @respx.mock
    async def test_api_error(self, adapter):
        respx.post("https://api.linkedin.com/rest/posts").mock(
            return_value=httpx.Response(422, text="Validation error")
        )

        result = await adapter.publish("Test", [], {}, CREDS)

        assert not result.success
        assert "Validation error" in result.error

    @respx.mock
    async def test_media_upload_fails(self, adapter, image_media):
        respx.post(
            "https://api.linkedin.com/rest/images", params__contains={"action": "initializeUpload"}
        ).mock(return_value=httpx.Response(500, text="Server Error"))

        result = await adapter.publish("Test", image_media, {}, CREDS)

        assert not result.success
        assert "upload failed" in result.error.lower()


class TestDelete:
    @respx.mock
    async def test_success(self, adapter):
        respx.delete(
            "https://api.linkedin.com/rest/posts/urn:li:share:12345"
        ).mock(return_value=httpx.Response(204))

        assert await adapter.delete("urn:li:share:12345", CREDS) is True

    @respx.mock
    async def test_failure(self, adapter):
        respx.delete(
            "https://api.linkedin.com/rest/posts/bad"
        ).mock(return_value=httpx.Response(404))

        assert await adapter.delete("bad", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self, adapter):
        respx.get("https://api.linkedin.com/v2/userinfo").mock(
            return_value=httpx.Response(200, json={"sub": "abc"})
        )

        assert await adapter.validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self, adapter):
        respx.get("https://api.linkedin.com/v2/userinfo").mock(
            return_value=httpx.Response(401)
        )

        assert await adapter.validate_credentials(CREDS) is False
