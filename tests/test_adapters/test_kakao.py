"""Tests for Kakao adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.kakao import KAKAO_API, KakaoAdapter

CREDS = {"access_token": "kakao_tok_123"}


def adapter() -> KakaoAdapter:
    return KakaoAdapter()


class TestPublish:
    @respx.mock
    async def test_story_note_success(self):
        respx.post(f"{KAKAO_API}/v1/api/story/post/note").mock(
            return_value=httpx.Response(200, json={
                "id": "story_123",
                "url": "https://story.kakao.com/story_123",
            })
        )
        result = await adapter().publish(
            "Hello Kakao!", [], {"target": "story"}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "story_123"
        assert result.url == "https://story.kakao.com/story_123"

    @respx.mock
    async def test_story_photo_success(self, image_media):
        respx.post(f"{KAKAO_API}/v1/api/story/upload/multi").mock(
            return_value=httpx.Response(200, json=[
                {"url": "https://kakao-img.example.com/uploaded.jpg"}
            ])
        )
        respx.post(f"{KAKAO_API}/v1/api/story/post/photo").mock(
            return_value=httpx.Response(200, json={
                "id": "photo_456",
                "url": "https://story.kakao.com/photo_456",
            })
        )
        result = await adapter().publish(
            "Photo post", image_media, {}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "photo_456"

    @respx.mock
    async def test_story_upload_fail_falls_back_to_note(self, image_media):
        respx.post(f"{KAKAO_API}/v1/api/story/upload/multi").mock(
            return_value=httpx.Response(500, text="Upload failed")
        )
        respx.post(f"{KAKAO_API}/v1/api/story/post/note").mock(
            return_value=httpx.Response(200, json={"id": "note_789"})
        )
        result = await adapter().publish(
            "Fallback text", image_media, {}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "note_789"

    @respx.mock
    async def test_story_post_failure(self):
        respx.post(f"{KAKAO_API}/v1/api/story/post/note").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success

    @respx.mock
    async def test_channel_success(self):
        respx.post(f"{KAKAO_API}/v1/api/talk/channel/message/send").mock(
            return_value=httpx.Response(200, json={"result_code": 0})
        )
        result = await adapter().publish(
            "Channel msg", [], {
                "target": "channel",
                "channel_id": "ch_001",
                "link_url": "https://example.com",
            }, CREDS,
        )
        assert result.success

    @respx.mock
    async def test_channel_api_error(self):
        respx.post(f"{KAKAO_API}/v1/api/talk/channel/message/send").mock(
            return_value=httpx.Response(200, json={
                "result_code": -401,
                "result_message": "Invalid channel",
            })
        )
        result = await adapter().publish(
            "fail", [], {"target": "channel"}, CREDS,
        )
        assert not result.success
        assert "Invalid channel" in result.error

    @respx.mock
    async def test_channel_http_error(self):
        respx.post(f"{KAKAO_API}/v1/api/talk/channel/message/send").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        result = await adapter().publish(
            "fail", [], {"target": "channel"}, CREDS,
        )
        assert not result.success


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.delete(f"{KAKAO_API}/v1/api/story/delete/mystory").mock(
            return_value=httpx.Response(200)
        )
        assert await adapter().delete("story_123", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.delete(f"{KAKAO_API}/v1/api/story/delete/mystory").mock(
            return_value=httpx.Response(404)
        )
        assert await adapter().delete("bad_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{KAKAO_API}/v2/user/me").mock(
            return_value=httpx.Response(200, json={"id": 12345})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{KAKAO_API}/v2/user/me").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
