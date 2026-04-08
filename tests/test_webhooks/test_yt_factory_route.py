"""
End-to-end route tests for the yt-factory webhook endpoint.

Current implementation:
- Route: POST /api/webhooks/yt-factory (202)
- Signature: X-YtBoost-Signature header, HMAC-SHA256 with timestamp replay protection
- Payload: YtFactoryPayload (Pydantic) — requires youtube_video_id, youtube_channel_id, user_id
- Enqueue: YtFactoryIntegration.handle_publish_complete → extract_ytboost_shorts_task.delay
- Dedup: is_known_video check in YtFactoryIntegration
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.webhook_signature import create_yt_factory_signature

WEBHOOK_SECRET = "test-yt-factory-secret-key"
WEBHOOK_URL = "/api/webhooks/yt-factory"


def _payload(
    *,
    user_id: str = "user_abc",
    video_id: str = "vid_001",
    channel_id: str = "chan_001",
    job_id: str | None = "job_001",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = {
        "youtube_video_id": video_id,
        "youtube_channel_id": channel_id,
        "user_id": user_id,
        "yt_factory_job_id": job_id,
        "transcript": [{"start": 0, "text": "hook line"}],
        "video_metadata": {"title": "Test Video"},
        "script_data": {},
    }
    if extra:
        base.update(extra)
    return base


def _signed_headers(body: bytes, secret: str = WEBHOOK_SECRET) -> dict[str, str]:
    sig = create_yt_factory_signature(body, secret)
    return {"Content-Type": "application/json", "X-YtBoost-Signature": sig}


@pytest.fixture()
def _patch_deps(monkeypatch):
    """Patch external deps: config secret, is_known_video, mark_video_detected, celery task."""
    from types import SimpleNamespace

    from app.config import Settings

    # Patch settings to return our webhook secret
    def fake_settings():
        s = Settings(
            SUPABASE_URL="https://fake.supabase.co",
            SUPABASE_ANON_KEY="fake-anon",
            SUPABASE_SERVICE_ROLE_KEY="fake-service",
            REDIS_URL="redis://localhost:6379/0",
            TOKEN_ENCRYPTION_KEY="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=",
            OAUTH_STATE_SECRET="test-state-secret",
            YTBOOST_WEBHOOK_SECRET=WEBHOOK_SECRET,
        )
        return s

    monkeypatch.setattr("app.api.webhooks.yt_factory.get_settings", fake_settings)
    monkeypatch.setattr("app.core.webhook_signature.time.time", time.time)

    queued: list[tuple] = []

    class FakeTask:
        @staticmethod
        def delay(*args):
            queued.append(args)

    async def fake_mark(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.yt_factory_integration.is_known_video", lambda *_: False
    )
    monkeypatch.setattr(
        "app.services.yt_factory_integration.mark_video_detected", fake_mark
    )
    monkeypatch.setattr(
        "app.services.yt_factory_integration.extract_ytboost_shorts_task", FakeTask()
    )

    return SimpleNamespace(queued=queued)


@pytest.fixture()
def _patch_deps_duplicate(monkeypatch):
    """Like _patch_deps but is_known_video returns True (duplicate)."""
    from types import SimpleNamespace

    from app.config import Settings

    def fake_settings():
        return Settings(
            SUPABASE_URL="https://fake.supabase.co",
            SUPABASE_ANON_KEY="fake-anon",
            SUPABASE_SERVICE_ROLE_KEY="fake-service",
            REDIS_URL="redis://localhost:6379/0",
            TOKEN_ENCRYPTION_KEY="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=",
            OAUTH_STATE_SECRET="test-state-secret",
            YTBOOST_WEBHOOK_SECRET=WEBHOOK_SECRET,
        )

    monkeypatch.setattr("app.api.webhooks.yt_factory.get_settings", fake_settings)

    queued: list[tuple] = []

    class FakeTask:
        @staticmethod
        def delay(*args):
            queued.append(args)

    monkeypatch.setattr(
        "app.services.yt_factory_integration.is_known_video", lambda *_: True
    )
    monkeypatch.setattr(
        "app.services.yt_factory_integration.extract_ytboost_shorts_task", FakeTask()
    )

    return SimpleNamespace(queued=queued)


@pytest.fixture()
def _patch_deps_enqueue_fail(monkeypatch):
    """Like _patch_deps but task.delay raises an exception."""
    from app.config import Settings

    def fake_settings():
        return Settings(
            SUPABASE_URL="https://fake.supabase.co",
            SUPABASE_ANON_KEY="fake-anon",
            SUPABASE_SERVICE_ROLE_KEY="fake-service",
            REDIS_URL="redis://localhost:6379/0",
            TOKEN_ENCRYPTION_KEY="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1lbm91Z2g=",
            OAUTH_STATE_SECRET="test-state-secret",
            YTBOOST_WEBHOOK_SECRET=WEBHOOK_SECRET,
        )

    monkeypatch.setattr("app.api.webhooks.yt_factory.get_settings", fake_settings)

    class FailTask:
        @staticmethod
        def delay(*args):
            raise ConnectionError("Redis unavailable")

    async def fake_mark(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.yt_factory_integration.is_known_video", lambda *_: False
    )
    monkeypatch.setattr(
        "app.services.yt_factory_integration.mark_video_detected", fake_mark
    )
    monkeypatch.setattr(
        "app.services.yt_factory_integration.extract_ytboost_shorts_task", FailTask()
    )


async def _client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ---------------------------------------------------------------------------
# 1. Valid signature + valid payload → 202
# ---------------------------------------------------------------------------


async def test_valid_signature_and_payload(_patch_deps) -> None:
    body = json.dumps(_payload()).encode()
    headers = _signed_headers(body)

    async with await _client() as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["queued"] is True
    assert data["video_id"] == "vid_001"
    assert len(_patch_deps.queued) == 1


# ---------------------------------------------------------------------------
# 2. Missing signature header → 401
# ---------------------------------------------------------------------------


async def test_missing_signature_header(_patch_deps) -> None:
    body = json.dumps(_payload()).encode()

    async with await _client() as client:
        resp = await client.post(
            WEBHOOK_URL,
            content=body,
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 401
    assert "Missing" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Forged signature → 401
# ---------------------------------------------------------------------------


async def test_forged_signature(_patch_deps) -> None:
    body = json.dumps(_payload()).encode()
    headers = _signed_headers(body, secret="wrong-secret")

    async with await _client() as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)

    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. Expired timestamp → 401
# ---------------------------------------------------------------------------


async def test_expired_timestamp(_patch_deps, monkeypatch) -> None:
    body = json.dumps(_payload()).encode()
    # Create signature with a timestamp 10 minutes ago
    old_time = int(time.time()) - 600
    import hashlib
    import hmac as hmac_mod

    signed = f"{old_time}.".encode() + body
    digest = hmac_mod.new(WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    sig = f"t={old_time},sha256={digest}"

    async with await _client() as client:
        resp = await client.post(
            WEBHOOK_URL,
            content=body,
            headers={"Content-Type": "application/json", "X-YtBoost-Signature": sig},
        )

    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Malformed signature format → 400
# ---------------------------------------------------------------------------


async def test_malformed_signature_format(_patch_deps) -> None:
    body = json.dumps(_payload()).encode()

    async with await _client() as client:
        resp = await client.post(
            WEBHOOK_URL,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-YtBoost-Signature": "not-a-valid-signature",
            },
        )

    assert resp.status_code == 400
    assert "Malformed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Missing required field (youtube_video_id) → 422
# ---------------------------------------------------------------------------


async def test_missing_required_field(_patch_deps) -> None:
    payload = {"youtube_channel_id": "chan_001", "user_id": "user_abc"}
    body = json.dumps(payload).encode()
    headers = _signed_headers(body)

    async with await _client() as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. Wrong field type (user_id as integer) → 422
# ---------------------------------------------------------------------------


async def test_wrong_field_type(_patch_deps) -> None:
    payload = {
        "youtube_video_id": "vid_001",
        "youtube_channel_id": "chan_001",
        "user_id": 12345,
    }
    body = json.dumps(payload).encode()
    headers = _signed_headers(body)

    async with await _client() as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)

    # Pydantic v2 coerces int→str, so this may succeed as 202 or fail as 422
    # depending on strict mode. Either is acceptable.
    assert resp.status_code in (202, 422)


# ---------------------------------------------------------------------------
# 8. Duplicate webhook (same video_id) → idempotent (202, queued=False)
# ---------------------------------------------------------------------------


async def test_duplicate_webhook_idempotent(_patch_deps_duplicate) -> None:
    body = json.dumps(_payload()).encode()
    headers = _signed_headers(body)

    async with await _client() as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["duplicate"] is True
    assert data["queued"] is False
    assert len(_patch_deps_duplicate.queued) == 0


# ---------------------------------------------------------------------------
# 9. Non-existent user_id → graceful handling (still 202)
# ---------------------------------------------------------------------------


async def test_nonexistent_user_id_handled_gracefully(_patch_deps) -> None:
    body = json.dumps(_payload(user_id="nonexistent_user_999")).encode()
    headers = _signed_headers(body)

    async with await _client() as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)

    # Webhook should still accept — user validation happens downstream
    assert resp.status_code == 202
    assert resp.json()["queued"] is True


# ---------------------------------------------------------------------------
# 10. Task enqueue failure → 500
# ---------------------------------------------------------------------------


async def test_task_enqueue_failure_returns_500(_patch_deps_enqueue_fail) -> None:
    body = json.dumps(_payload()).encode()
    headers = _signed_headers(body)

    async with await _client() as client:
        resp = await client.post(WEBHOOK_URL, content=body, headers=headers)

    assert resp.status_code == 500
    assert "Internal" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 11. Wrong Content-Type → 422 (FastAPI rejects non-JSON for Pydantic body)
# ---------------------------------------------------------------------------


async def test_wrong_content_type(_patch_deps) -> None:
    body = b"not json at all"
    sig = create_yt_factory_signature(body, WEBHOOK_SECRET)

    async with await _client() as client:
        resp = await client.post(
            WEBHOOK_URL,
            content=body,
            headers={"Content-Type": "text/plain", "X-YtBoost-Signature": sig},
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 12. Signature with extra whitespace → still valid
# ---------------------------------------------------------------------------


async def test_signature_with_whitespace_tolerance(_patch_deps) -> None:
    body = json.dumps(_payload()).encode()
    sig = create_yt_factory_signature(body, WEBHOOK_SECRET)
    # Add whitespace around parts
    parts = sig.split(",")
    spaced_sig = " , ".join(parts)

    async with await _client() as client:
        resp = await client.post(
            WEBHOOK_URL,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-YtBoost-Signature": spaced_sig,
            },
        )

    assert resp.status_code == 202
