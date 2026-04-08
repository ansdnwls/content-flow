"""Tests for Threads adapter."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.adapters.threads import ThreadsAdapter

CREDS = {"access_token": "fake_token", "threads_user_id": "user_001"}


@pytest.fixture
def adapter() -> ThreadsAdapter:
    return ThreadsAdapter()


class TestPublish:
    @respx.mock
    async def test_text_only(self, adapter):
        # Create container
        respx.post("https://graph.threads.net/v1.0/user_001/threads").mock(
            return_value=httpx.Response(200, json={"id": "container_001"})
        )
        # Publish
        respx.post("https://graph.threads.net/v1.0/user_001/threads_publish").mock(
            return_value=httpx.Response(200, json={"id": "thread_001"})
        )

        result = await adapter.publish("Hello Threads", [], {}, CREDS)

        assert result.success
        assert result.platform_post_id == "thread_001"
        assert "threads.net" in result.url

    @respx.mock
    async def test_with_image(self, adapter, image_media):
        respx.post("https://graph.threads.net/v1.0/user_001/threads").mock(
            return_value=httpx.Response(200, json={"id": "container_002"})
        )
        respx.post("https://graph.threads.net/v1.0/user_001/threads_publish").mock(
            return_value=httpx.Response(200, json={"id": "thread_002"})
        )

        result = await adapter.publish("Image thread", image_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "thread_002"

    @respx.mock
    async def test_with_video_and_polling(self, adapter, video_media):
        # Create container
        respx.post("https://graph.threads.net/v1.0/user_001/threads").mock(
            return_value=httpx.Response(200, json={"id": "container_003"})
        )
        # Poll status: IN_PROGRESS → FINISHED
        respx.get("https://graph.threads.net/v1.0/container_003").mock(
            side_effect=[
                httpx.Response(200, json={"status": "IN_PROGRESS"}),
                httpx.Response(200, json={"status": "FINISHED"}),
            ]
        )
        # Publish
        respx.post("https://graph.threads.net/v1.0/user_001/threads_publish").mock(
            return_value=httpx.Response(200, json={"id": "thread_003"})
        )

        result = await adapter.publish("Video thread", video_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "thread_003"

    @respx.mock
    async def test_carousel(self, adapter, multi_image_media):
        # Create child containers
        respx.post("https://graph.threads.net/v1.0/user_001/threads").mock(
            side_effect=[
                # 3 child containers
                httpx.Response(200, json={"id": "child_1"}),
                httpx.Response(200, json={"id": "child_2"}),
                httpx.Response(200, json={"id": "child_3"}),
                # Carousel container
                httpx.Response(200, json={"id": "carousel_container"}),
            ]
        )
        # Publish
        respx.post("https://graph.threads.net/v1.0/user_001/threads_publish").mock(
            return_value=httpx.Response(200, json={"id": "thread_carousel"})
        )

        result = await adapter.publish("Carousel", multi_image_media, {}, CREDS)

        assert result.success
        assert result.platform_post_id == "thread_carousel"

    @respx.mock
    async def test_container_creation_fails(self, adapter):
        respx.post("https://graph.threads.net/v1.0/user_001/threads").mock(
            return_value=httpx.Response(400, text="Bad request")
        )

        result = await adapter.publish("test", [], {}, CREDS)

        assert not result.success
        assert "Bad request" in result.error

    @respx.mock
    async def test_publish_step_fails(self, adapter):
        respx.post("https://graph.threads.net/v1.0/user_001/threads").mock(
            return_value=httpx.Response(200, json={"id": "container_fail"})
        )
        respx.post("https://graph.threads.net/v1.0/user_001/threads_publish").mock(
            return_value=httpx.Response(500, text="Internal error")
        )

        result = await adapter.publish("test", [], {}, CREDS)

        assert not result.success
        assert "Internal error" in result.error

    @respx.mock
    async def test_reply_control_option(self, adapter):
        respx.post("https://graph.threads.net/v1.0/user_001/threads").mock(
            return_value=httpx.Response(200, json={"id": "c_rc"})
        )
        respx.post("https://graph.threads.net/v1.0/user_001/threads_publish").mock(
            return_value=httpx.Response(200, json={"id": "t_rc"})
        )

        result = await adapter.publish(
            "reply test", [], {"reply_control": "accounts_you_follow"}, CREDS
        )

        assert result.success


class TestDelete:
    async def test_returns_false(self, adapter):
        """Threads API does not support programmatic deletion."""
        assert await adapter.delete("any_id", CREDS) is False


class TestValidateCredentials:
    @respx.mock
    async def test_valid(self, adapter):
        respx.get("https://graph.threads.net/v1.0/me").mock(
            return_value=httpx.Response(200, json={"id": "user_001", "username": "test"})
        )

        assert await adapter.validate_credentials(CREDS) is True

    @respx.mock
    async def test_invalid(self, adapter):
        respx.get("https://graph.threads.net/v1.0/me").mock(
            return_value=httpx.Response(401)
        )

        assert await adapter.validate_credentials(CREDS) is False
