"""Tests for the ContentFlow Python SDK — sync and async clients."""

from __future__ import annotations

import hmac
from hashlib import sha256

import httpx
import pytest
import respx

from contentflow import AsyncContentFlow, ContentFlow, webhooks

BASE = "https://api.contentflow.dev"
API_KEY = "cf_live_test_key_1234"


# ── Sync client ───────────────────────────────────────────────────


class TestSyncPosts:
    @respx.mock
    def test_create(self):
        respx.post(f"{BASE}/api/v1/posts").mock(
            return_value=httpx.Response(201, json={
                "id": "post_1", "status": "pending", "platforms": {"youtube": {"status": "pending"}}
            })
        )
        with ContentFlow(api_key=API_KEY) as cf:
            post = cf.posts.create(text="Hello", platforms=["youtube"])
            assert post["id"] == "post_1"
            assert post["status"] == "pending"

    @respx.mock
    def test_create_with_media(self):
        respx.post(f"{BASE}/api/v1/posts").mock(
            return_value=httpx.Response(201, json={
                "id": "post_2", "status": "scheduled", "platforms": {}
            })
        )
        with ContentFlow(api_key=API_KEY) as cf:
            post = cf.posts.create(
                text="Video post",
                platforms=["youtube", "tiktok"],
                media_urls=["https://example.com/video.mp4"],
                media_type="video",
                scheduled_for="2026-04-10T09:00:00Z",
                platform_options={"youtube": {"title": "My Video"}},
            )
            assert post["id"] == "post_2"

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/api/v1/posts/post_1").mock(
            return_value=httpx.Response(200, json={"id": "post_1", "status": "published"})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            post = cf.posts.get("post_1")
            assert post["status"] == "published"

    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/api/v1/posts").mock(
            return_value=httpx.Response(200, json={
                "data": [{"id": "p1"}, {"id": "p2"}], "total": 2, "page": 1, "limit": 20
            })
        )
        with ContentFlow(api_key=API_KEY) as cf:
            result = cf.posts.list(page=1, limit=20)
            assert result["total"] == 2
            assert len(result["data"]) == 2

    @respx.mock
    def test_list_with_status_filter(self):
        respx.get(f"{BASE}/api/v1/posts").mock(
            return_value=httpx.Response(200, json={
                "data": [], "total": 0, "page": 1, "limit": 20
            })
        )
        with ContentFlow(api_key=API_KEY) as cf:
            result = cf.posts.list(status="published")
            assert result["total"] == 0

    @respx.mock
    def test_cancel(self):
        respx.delete(f"{BASE}/api/v1/posts/post_1").mock(
            return_value=httpx.Response(200, json={"id": "post_1", "status": "cancelled"})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            post = cf.posts.cancel("post_1")
            assert post["status"] == "cancelled"

    @respx.mock
    def test_api_error_raises(self):
        respx.get(f"{BASE}/api/v1/posts/bad_id").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            with pytest.raises(httpx.HTTPStatusError):
                cf.posts.get("bad_id")


class TestSyncVideos:
    @respx.mock
    def test_generate(self):
        respx.post(f"{BASE}/api/v1/videos/generate").mock(
            return_value=httpx.Response(201, json={
                "id": "vid_1", "status": "queued", "estimated_minutes": 8
            })
        )
        with ContentFlow(api_key=API_KEY) as cf:
            video = cf.videos.generate(topic="DUI 3-strike laws", mode="legal")
            assert video["id"] == "vid_1"
            assert video["status"] == "queued"

    @respx.mock
    def test_generate_with_auto_publish(self):
        respx.post(f"{BASE}/api/v1/videos/generate").mock(
            return_value=httpx.Response(201, json={"id": "vid_2", "status": "queued"})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            video = cf.videos.generate(
                topic="Test",
                auto_publish={"platforms": ["youtube", "tiktok"]},
            )
            assert video["id"] == "vid_2"

    @respx.mock
    def test_get(self):
        respx.get(f"{BASE}/api/v1/videos/vid_1").mock(
            return_value=httpx.Response(200, json={"id": "vid_1", "status": "completed"})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            video = cf.videos.get("vid_1")
            assert video["status"] == "completed"


class TestSyncAccounts:
    @respx.mock
    def test_list(self):
        respx.get(f"{BASE}/api/v1/accounts").mock(
            return_value=httpx.Response(200, json={"accounts": [{"platform": "youtube"}]})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            result = cf.accounts.list()
            assert len(result["accounts"]) == 1

    @respx.mock
    def test_connect(self):
        respx.post(f"{BASE}/api/v1/accounts/connect/youtube").mock(
            return_value=httpx.Response(200, json={"authorize_url": "https://accounts.google.com/..."})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            result = cf.accounts.connect("youtube")
            assert "authorize_url" in result


class TestSyncAnalytics:
    @respx.mock
    def test_get_all(self):
        respx.get(f"{BASE}/api/v1/analytics").mock(
            return_value=httpx.Response(200, json={"total_posts": 42})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            result = cf.analytics.get()
            assert result["total_posts"] == 42

    @respx.mock
    def test_get_platform(self):
        respx.get(f"{BASE}/api/v1/analytics/youtube").mock(
            return_value=httpx.Response(200, json={"platform": "youtube", "views": 1000})
        )
        with ContentFlow(api_key=API_KEY) as cf:
            result = cf.analytics.get(platform="youtube")
            assert result["platform"] == "youtube"


class TestSyncClientSetup:
    def test_api_key_header(self):
        cf = ContentFlow(api_key="cf_live_test")
        assert cf._client.headers["X-API-Key"] == "cf_live_test"
        cf.close()

    def test_custom_base_url(self):
        cf = ContentFlow(api_key="k", base_url="https://custom.api.dev")
        assert cf._base_url == "https://custom.api.dev"
        cf.close()

    def test_context_manager(self):
        with ContentFlow(api_key="k") as cf:
            assert cf.posts is not None


# ── Async client ──────���───────────────────────────────────────────


class TestAsyncPosts:
    @respx.mock
    async def test_create(self):
        respx.post(f"{BASE}/api/v1/posts").mock(
            return_value=httpx.Response(201, json={
                "id": "post_a", "status": "pending", "platforms": {}
            })
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            post = await cf.posts.create(text="Async hello", platforms=["tiktok"])
            assert post["id"] == "post_a"

    @respx.mock
    async def test_get(self):
        respx.get(f"{BASE}/api/v1/posts/post_a").mock(
            return_value=httpx.Response(200, json={"id": "post_a", "status": "published"})
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            post = await cf.posts.get("post_a")
            assert post["status"] == "published"

    @respx.mock
    async def test_list(self):
        respx.get(f"{BASE}/api/v1/posts").mock(
            return_value=httpx.Response(200, json={
                "data": [{"id": "p1"}], "total": 1, "page": 1, "limit": 20
            })
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            result = await cf.posts.list()
            assert result["total"] == 1

    @respx.mock
    async def test_cancel(self):
        respx.delete(f"{BASE}/api/v1/posts/post_a").mock(
            return_value=httpx.Response(200, json={"id": "post_a", "status": "cancelled"})
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            post = await cf.posts.cancel("post_a")
            assert post["status"] == "cancelled"


class TestAsyncVideos:
    @respx.mock
    async def test_generate(self):
        respx.post(f"{BASE}/api/v1/videos/generate").mock(
            return_value=httpx.Response(201, json={"id": "vid_a", "status": "queued"})
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            video = await cf.videos.generate(topic="Test topic")
            assert video["id"] == "vid_a"

    @respx.mock
    async def test_get(self):
        respx.get(f"{BASE}/api/v1/videos/vid_a").mock(
            return_value=httpx.Response(200, json={"id": "vid_a", "status": "completed"})
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            video = await cf.videos.get("vid_a")
            assert video["status"] == "completed"


class TestAsyncAccounts:
    @respx.mock
    async def test_list(self):
        respx.get(f"{BASE}/api/v1/accounts").mock(
            return_value=httpx.Response(200, json={"accounts": []})
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            result = await cf.accounts.list()
            assert result["accounts"] == []

    @respx.mock
    async def test_connect(self):
        respx.post(f"{BASE}/api/v1/accounts/connect/tiktok").mock(
            return_value=httpx.Response(200, json={"authorize_url": "https://tiktok.com/..."})
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            result = await cf.accounts.connect("tiktok")
            assert "authorize_url" in result


class TestAsyncAnalytics:
    @respx.mock
    async def test_get(self):
        respx.get(f"{BASE}/api/v1/analytics").mock(
            return_value=httpx.Response(200, json={"total_posts": 10})
        )
        async with AsyncContentFlow(api_key=API_KEY) as cf:
            result = await cf.analytics.get()
            assert result["total_posts"] == 10


class TestAsyncClientSetup:
    async def test_context_manager(self):
        async with AsyncContentFlow(api_key="k") as cf:
            assert cf.posts is not None


class TestWebhookHelpers:
    def test_verify_signature_accepts_valid_payload(self):
        body = '{"event":"post.published","data":{"id":"p1"}}'
        timestamp = "1712505600"
        secret = "whsec_test"
        signature = "sha256=" + hmac.new(
            secret.encode(),
            f"{timestamp}.{body}".encode(),
            sha256,
        ).hexdigest()

        assert webhooks.verify_signature(
            body,
            signature,
            secret,
            timestamp,
            current_time=1712505601,
        ) is True

    def test_verify_signature_rejects_invalid_signature(self):
        assert webhooks.verify_signature(
            "{}",
            "sha256=deadbeef",
            "whsec_test",
            "1712505600",
            current_time=1712505600,
        ) is False

    def test_verify_signature_rejects_stale_timestamp(self):
        body = "{}"
        timestamp = "1712505600"
        secret = "whsec_test"
        signature = "sha256=" + hmac.new(
            secret.encode(),
            f"{timestamp}.{body}".encode(),
            sha256,
        ).hexdigest()

        assert webhooks.verify_signature(
            body,
            signature,
            secret,
            timestamp,
            current_time=1712506201,
            tolerance_seconds=300,
        ) is False
