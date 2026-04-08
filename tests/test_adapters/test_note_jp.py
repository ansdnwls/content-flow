"""Tests for note.com (Japan) adapter."""

from __future__ import annotations

import httpx
import respx

from app.adapters.note_jp import NOTE_API, NoteJpAdapter

CREDS = {"access_token": "note_tok_123"}


def adapter() -> NoteJpAdapter:
    return NoteJpAdapter()


class TestPublish:
    @respx.mock
    async def test_text_post_success(self):
        respx.post(f"{NOTE_API}/v3/notes").mock(
            return_value=httpx.Response(201, json={
                "data": {
                    "id": 99001,
                    "key": "n1234abcd",
                    "user": {"urlname": "testwriter"},
                }
            })
        )
        result = await adapter().publish(
            "Hello note.com!", [], {"title": "Test Article"}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "99001"
        assert result.url == "https://note.com/testwriter/n/n1234abcd"

    @respx.mock
    async def test_with_image(self, image_media):
        respx.post(f"{NOTE_API}/v3/notes").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "id": 99002,
                    "key": "n5678efgh",
                    "user": {"urlname": "imgwriter"},
                }
            })
        )
        result = await adapter().publish(
            "Image article", image_media, {"title": "Photos"}, CREDS,
        )
        assert result.success
        assert result.platform_post_id == "99002"

    @respx.mock
    async def test_with_video(self, video_media):
        respx.post(f"{NOTE_API}/v3/notes").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "id": 99003,
                    "key": "n9999zzzz",
                    "user": {"urlname": "vidwriter"},
                }
            })
        )
        result = await adapter().publish(
            "Video article", video_media, {"type": "MovieNote"}, CREDS,
        )
        assert result.success

    @respx.mock
    async def test_with_options(self):
        respx.post(f"{NOTE_API}/v3/notes").mock(
            return_value=httpx.Response(201, json={
                "data": {"id": 99004, "key": "nopt1234", "user": {"urlname": "u"}}
            })
        )
        result = await adapter().publish(
            "Paid post", [], {
                "title": "Premium",
                "status": "draft",
                "price": 500,
                "hashtags": ["tech", "python"],
            }, CREDS,
        )
        assert result.success

    @respx.mock
    async def test_no_user_slug_returns_no_url(self):
        respx.post(f"{NOTE_API}/v3/notes").mock(
            return_value=httpx.Response(201, json={
                "data": {"id": 99005, "key": "nnouser"}
            })
        )
        result = await adapter().publish("text", [], {}, CREDS)
        assert result.success
        assert result.url is None

    @respx.mock
    async def test_http_error(self):
        respx.post(f"{NOTE_API}/v3/notes").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        result = await adapter().publish("fail", [], {}, CREDS)
        assert not result.success
        assert "Forbidden" in result.error


class TestDelete:
    @respx.mock
    async def test_success(self):
        respx.delete(f"{NOTE_API}/v3/notes/99001").mock(
            return_value=httpx.Response(204)
        )
        assert await adapter().delete("99001", CREDS) is True

    @respx.mock
    async def test_failure(self):
        respx.delete(f"{NOTE_API}/v3/notes/bad_id").mock(
            return_value=httpx.Response(404)
        )
        assert await adapter().delete("bad_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self):
        respx.get(f"{NOTE_API}/v2/users/me").mock(
            return_value=httpx.Response(200, json={"data": {"id": 1}})
        )
        assert await adapter().validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self):
        respx.get(f"{NOTE_API}/v2/users/me").mock(
            return_value=httpx.Response(401)
        )
        assert await adapter().validate_credentials(CREDS) is False
