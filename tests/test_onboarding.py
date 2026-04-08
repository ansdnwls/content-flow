"""Tests for onboarding flow API."""

from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


def _setup(monkeypatch):
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    fake_sb.insert_row("users", {
        "id": user_id,
        "email": "onboard@example.com",
        "plan": "free",
        "email_verified": False,
        "onboarding_completed": False,
        "onboarding_steps": {},
    })
    issued, record = build_api_key_record(user_id=uuid4(), name="ob")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    def fake_get_supabase():
        return fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.onboarding.get_supabase", fake_get_supabase)
    return fake_sb, user_id, issued.raw_key


async def test_onboarding_status(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get("/api/v1/onboarding/status")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["steps"]) == 5
    assert body["progress"] >= 0


async def test_skip_step(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post("/api/v1/onboarding/skip/first_video")

    assert resp.status_code == 200
    body = resp.json()
    video_step = next(s for s in body["steps"] if s["id"] == "first_video")
    assert video_step["completed"] is True


async def test_complete_onboarding(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post("/api/v1/onboarding/complete")

    assert resp.status_code == 200
    assert resp.json()["completed"] is True

    user = next(r for r in fake_sb.tables["users"] if r["id"] == user_id)
    assert user["onboarding_completed"] is True
