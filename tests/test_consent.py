"""Consent management API tests — GDPR Art. 7."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


@pytest.fixture()
def authed_client(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeSupabase, str, str]:
    fake = FakeSupabase()
    for mod in (
        "app.api.deps",
        "app.api.v1.consent",
        "app.core.billing",
        "app.core.audit",
    ):
        monkeypatch.setattr(f"{mod}.get_supabase", lambda: fake)
    monkeypatch.setattr(
        "app.core.workspaces.resolve_workspace_id_for_user",
        lambda *a, **kw: None,
    )

    user_id = str(uuid4())
    fake.table("users").insert({
        "id": user_id,
        "email": "consent@test.com",
        "plan": "build",
        "is_active": True,
        "default_workspace_id": None,
    }).execute()

    issued, record = build_api_key_record(user_id=uuid4(), name="ck")
    record["user_id"] = user_id
    fake.table("api_keys").insert(record).execute()

    return fake, issued.raw_key, user_id


@pytest.mark.anyio()
async def test_get_consents_empty(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/api/v1/consent",
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    consents = {item["purpose"]: item for item in resp.json()["consents"]}
    assert consents["essential"]["granted"] is True
    assert consents["analytics"]["granted"] is False


@pytest.mark.anyio()
async def test_grant_consent(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/consent/grant",
            json={"purposes": ["analytics", "marketing"]},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["updated"]) == {"analytics", "marketing"}


@pytest.mark.anyio()
async def test_revoke_consent(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        # Grant first
        await client.post(
            "/api/v1/consent/grant",
            json={"purposes": ["analytics"]},
            headers={"X-API-Key": key},
        )
        # Revoke
        resp = await client.post(
            "/api/v1/consent/revoke",
            json={"purposes": ["analytics"]},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    assert "analytics" in resp.json()["updated"]


@pytest.mark.anyio()
async def test_revoke_essential_ignored(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    """Essential consent cannot be revoked."""
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/consent/revoke",
            json={"purposes": ["essential"]},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    assert resp.json()["updated"] == []


@pytest.mark.anyio()
async def test_consent_history(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        await client.post(
            "/api/v1/consent/grant",
            json={"purposes": ["analytics"]},
            headers={"X-API-Key": key},
        )
        resp = await client.get(
            "/api/v1/consent/history",
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    assert len(resp.json()["history"]) >= 1


@pytest.mark.anyio()
async def test_invalid_purpose_ignored(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    """Invalid purposes are rejected so consent state stays explicit."""
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/consent/grant",
            json={"purposes": ["nonexistent_purpose"]},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 400
    assert "Invalid consent purposes" in resp.json()["detail"]
