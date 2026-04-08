"""Integration tests for POST /api/v1/posts/bulk."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase

BULK_URL = "/api/v1/posts/bulk"


def _make_post(
    text: str = "test",
    platforms: list[str] | None = None,
    scheduled_for: str | None = None,
) -> dict:
    return {
        "text": text,
        "platforms": platforms or ["youtube"],
        "media_urls": [],
        "media_type": "text",
        "scheduled_for": scheduled_for,
        "platform_options": {},
    }


@pytest.fixture()
def setup():
    """Create a fake Supabase, user, API key, and mock Celery task."""
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    fake_sb.insert_row(
        "users",
        {"id": user_id, "email": "bulk@example.com", "plan": "scale"},
    )

    issued, record = build_api_key_record(user_id=uuid4(), name="bulk-test")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    queued: list[tuple[str, str]] = []

    class FakeTask:
        @staticmethod
        def delay(post_id: str, owner_id: str) -> None:
            queued.append((post_id, owner_id))

        @staticmethod
        def s(post_id: str, owner_id: str):
            return (post_id, owner_id)

    mock_group = MagicMock()
    mock_group.return_value.apply_async = MagicMock()

    return SimpleNamespace(
        fake_sb=fake_sb,
        user_id=user_id,
        raw_key=issued.raw_key,
        queued=queued,
        fake_task=FakeTask,
        mock_group=mock_group,
    )


@pytest.fixture()
def patched_app(setup, monkeypatch):
    """Monkeypatch Supabase, billing, Celery, and throttle for tests."""

    def fake_get_supabase():
        return setup.fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.core.billing.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.posts.publish_post_task", setup.fake_task)
    monkeypatch.setattr("app.api.v1.posts.bulk_enqueue", lambda pairs: None)

    return setup


async def test_bulk_all_or_nothing_success(patched_app) -> None:
    """3 posts in all_or_nothing mode — all should be created."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": patched_app.raw_key},
    ) as client:
        resp = await client.post(
            BULK_URL,
            json={
                "posts": [_make_post(f"post-{i}") for i in range(3)],
                "mode": "all_or_nothing",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["total_submitted"] == 3
    assert body["total_created"] == 3
    assert body["total_failed"] == 0
    assert all(r["status"] == "created" for r in body["results"])


async def test_bulk_partial_mode_with_failure(patched_app, monkeypatch) -> None:
    """In partial mode, individual failures don't stop the batch."""
    call_count = 0

    from app.api.v1 import posts as posts_module

    original_fn = posts_module.create_internal_post

    async def flaky_create(owner_id, req, *, skip_enqueue=False):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulated failure")
        return await original_fn(owner_id, req, skip_enqueue=skip_enqueue)

    monkeypatch.setattr(posts_module, "create_internal_post", flaky_create)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": patched_app.raw_key},
    ) as client:
        resp = await client.post(
            BULK_URL,
            json={
                "posts": [_make_post(f"p-{i}") for i in range(3)],
                "mode": "partial",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["total_created"] == 2
    assert body["total_failed"] == 1
    failed = [r for r in body["results"] if r["status"] == "failed"]
    assert len(failed) == 1
    assert "Simulated failure" in failed[0]["error"]


async def test_bulk_all_or_nothing_quota_exceeded(patched_app, monkeypatch) -> None:
    """all_or_nothing with insufficient quota returns 402."""
    # Override billing to return only 1 remaining
    async def limited_billing(owner_id, plan, count):
        return 1

    monkeypatch.setattr("app.api.v1.posts.check_post_limit_bulk", limited_billing)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": patched_app.raw_key},
    ) as client:
        resp = await client.post(
            BULK_URL,
            json={
                "posts": [_make_post() for _ in range(3)],
                "mode": "all_or_nothing",
            },
        )

    assert resp.status_code == 402


async def test_bulk_partial_quota_creates_subset(patched_app, monkeypatch) -> None:
    """partial mode with limited quota creates only allowed posts."""
    async def limited_billing(owner_id, plan, count):
        return 2

    monkeypatch.setattr("app.api.v1.posts.check_post_limit_bulk", limited_billing)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": patched_app.raw_key},
    ) as client:
        resp = await client.post(
            BULK_URL,
            json={
                "posts": [_make_post(f"p-{i}") for i in range(4)],
                "mode": "partial",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["total_created"] == 2
    assert body["total_failed"] == 2
    for r in body["results"][2:]:
        assert r["status"] == "failed"
        assert "Quota exceeded" in r["error"]


async def test_bulk_throttle_stagger(patched_app) -> None:
    """YouTube posts should get 5-minute staggering applied."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": patched_app.raw_key},
    ) as client:
        resp = await client.post(
            BULK_URL,
            json={
                "posts": [
                    _make_post("yt-1", platforms=["youtube"]),
                    _make_post("yt-2", platforms=["youtube"]),
                ],
                "mode": "all_or_nothing",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    first = body["results"][0]["post"]
    second = body["results"][1]["post"]
    # First post should be immediate (pending), second should be scheduled
    assert first["status"] == "pending"
    assert second["status"] == "scheduled"
    assert second["scheduled_for"] is not None


async def test_bulk_empty_list_rejected(patched_app) -> None:
    """Empty posts list returns 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": patched_app.raw_key},
    ) as client:
        resp = await client.post(
            BULK_URL,
            json={"posts": [], "mode": "all_or_nothing"},
        )

    assert resp.status_code == 422


async def test_bulk_over_100_rejected(patched_app) -> None:
    """More than 100 posts returns 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": patched_app.raw_key},
    ) as client:
        resp = await client.post(
            BULK_URL,
            json={
                "posts": [_make_post(f"p-{i}") for i in range(101)],
                "mode": "all_or_nothing",
            },
        )

    assert resp.status_code == 422
