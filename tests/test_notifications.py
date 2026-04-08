"""Tests for in-app notifications API."""

from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase

BASE = "/api/v1/notifications"


def _setup(monkeypatch):
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    fake_sb.insert_row("users", {
        "id": user_id,
        "email": "notify@example.com",
        "plan": "free",
    })
    issued, record = build_api_key_record(user_id=uuid4(), name="ntf")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    def fake_get_supabase():
        return fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr(
        "app.services.notification_service.get_supabase", fake_get_supabase,
    )
    return fake_sb, user_id, issued.raw_key


def _insert_notification(fake_sb, user_id, **overrides):
    row = {
        "id": str(uuid4()),
        "user_id": user_id,
        "type": "post_published",
        "title": "Post published",
        "body": "Your post was published successfully.",
        "link_url": None,
        "read_at": None,
        "created_at": "2026-04-09T00:00:00+00:00",
    }
    row.update(overrides)
    fake_sb.insert_row("notifications", row)
    return row


async def test_list_empty(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(BASE)

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["total"] == 0


async def test_list_returns_notifications(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    _insert_notification(fake_sb, user_id, title="First")
    _insert_notification(fake_sb, user_id, title="Second")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(BASE)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2


async def test_list_unread_only(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    _insert_notification(fake_sb, user_id, title="Unread")
    _insert_notification(
        fake_sb, user_id, title="Read",
        read_at="2026-04-09T01:00:00+00:00",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(BASE, params={"unread_only": "true"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["title"] == "Unread"


async def test_unread_count(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    _insert_notification(fake_sb, user_id)
    _insert_notification(fake_sb, user_id)
    _insert_notification(
        fake_sb, user_id, read_at="2026-04-09T01:00:00+00:00",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(f"{BASE}/unread-count")

    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 2


async def test_mark_read(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    notif = _insert_notification(fake_sb, user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(f"{BASE}/{notif['id']}/read")

    assert resp.status_code == 200
    body = resp.json()
    assert body["read_at"] is not None


async def test_mark_read_not_found(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(f"{BASE}/{uuid4()}/read")

    assert resp.status_code == 404


async def test_mark_all_read(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    _insert_notification(fake_sb, user_id)
    _insert_notification(fake_sb, user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(f"{BASE}/read-all")

    assert resp.status_code == 200
    assert resp.json()["updated"] == 2


async def test_delete_notification(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    notif = _insert_notification(fake_sb, user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.delete(f"{BASE}/{notif['id']}")

    assert resp.status_code == 204


async def test_delete_not_found(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.delete(f"{BASE}/{uuid4()}")

    assert resp.status_code == 404


async def test_other_user_cannot_read(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    other_user_id = str(uuid4())
    notif = _insert_notification(fake_sb, other_user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(f"{BASE}/{notif['id']}/read")

    assert resp.status_code == 404


async def test_create_notification_service(monkeypatch) -> None:
    fake_sb, user_id, _raw_key = _setup(monkeypatch)

    from app.services.notification_service import create_notification

    result = create_notification(
        user_id=user_id,
        type="video_ready",
        title="Video ready",
        body="Your video has been generated.",
        link_url="/videos/123",
    )
    assert result["user_id"] == user_id
    assert result["type"] == "video_ready"
    assert result["link_url"] == "/videos/123"
