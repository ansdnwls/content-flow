"""Tests for email verification flow."""

from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.api.v1.email_verify import _create_verify_token
from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase

VERIFY_URL = "/api/v1/auth/verify-email"


def _setup(monkeypatch):
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    fake_sb.insert_row("users", {
        "id": user_id,
        "email": "verify@example.com",
        "plan": "free",
        "email_verified": False,
    })
    issued, record = build_api_key_record(user_id=uuid4(), name="ev")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    def fake_get_supabase():
        return fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.email_verify.get_supabase", fake_get_supabase)

    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "test")

    return fake_sb, user_id, issued.raw_key


async def test_request_verification(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(f"{VERIFY_URL}/request")

    assert resp.status_code == 200
    body = resp.json()
    assert "verify_url" in body
    assert "token=" in body["verify_url"]


async def test_confirm_verification(monkeypatch) -> None:
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    token = _create_verify_token(user_id, "verify@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            f"{VERIFY_URL}/confirm",
            json={"token": token},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    assert body["email"] == "verify@example.com"

    user = next(r for r in fake_sb.tables["users"] if r["id"] == user_id)
    assert user["email_verified"] is True


async def test_confirm_invalid_token(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            f"{VERIFY_URL}/confirm",
            json={"token": "invalid.jwt.token"},
        )

    assert resp.status_code == 401


async def test_confirm_wrong_user(monkeypatch) -> None:
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)
    other_id = str(uuid4())
    token = _create_verify_token(other_id, "other@example.com")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            f"{VERIFY_URL}/confirm",
            json={"token": token},
        )

    assert resp.status_code == 401
