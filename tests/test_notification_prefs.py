"""Tests for notification preferences API."""

from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase

PREFS_URL = "/api/v1/notifications/preferences"


def _setup(monkeypatch):
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    fake_sb.insert_row("users", {
        "id": user_id,
        "email": "prefs@example.com",
        "plan": "free",
    })
    issued, record = build_api_key_record(user_id=uuid4(), name="np")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    def fake_get_supabase():
        return fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr(
        "app.api.v1.notifications.get_supabase", fake_get_supabase,
    )
    return fake_sb, user_id, issued.raw_key


async def test_get_default_preferences(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(PREFS_URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["product_updates"] is True
    assert body["billing"] is True
    assert body["security"] is True
    assert body["monthly_summary"] is True
    assert body["webhook_alerts"] is True


async def test_update_preferences(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        # First call creates defaults
        await client.get(PREFS_URL)
        # Update some
        resp = await client.patch(
            PREFS_URL,
            json={"monthly_summary": False, "webhook_alerts": False},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["monthly_summary"] is False
    assert body["webhook_alerts"] is False
    assert body["billing"] is True


async def test_partial_update_preserves_others(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        await client.get(PREFS_URL)
        await client.patch(PREFS_URL, json={"billing": False})
        resp = await client.get(PREFS_URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["billing"] is False
    assert body["security"] is True
