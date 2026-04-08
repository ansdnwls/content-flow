"""GDPR Privacy Rights API tests — Art. 15-21."""

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
        "app.api.v1.privacy",
        "app.api.v1.posts",
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
        "email": "gdpr@test.com",
        "full_name": "Test User",
        "plan": "build",
        "is_active": True,
        "default_workspace_id": None,
        "data_processing_restricted": False,
        "deletion_scheduled_at": None,
    }).execute()

    issued, record = build_api_key_record(user_id=uuid4(), name="gk")
    record["user_id"] = user_id
    fake.table("api_keys").insert(record).execute()

    return fake, issued.raw_key, user_id


@pytest.mark.anyio()
async def test_get_my_data(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    fake, key, user_id = authed_client
    fake.table("posts").insert({
        "owner_id": user_id,
        "text": "hello",
        "status": "published",
    }).execute()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/api/v1/privacy/me",
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"]["email"] == "gdpr@test.com"
    assert data["posts_count"] == 1


@pytest.mark.anyio()
async def test_update_profile(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.patch(
            "/api/v1/privacy/me",
            json={"full_name": "New Name"},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True
    assert "full_name" in resp.json()["fields"]


@pytest.mark.anyio()
async def test_request_export(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    fake, key, user_id = authed_client
    fake.table("posts").insert({
        "owner_id": user_id,
        "text": "hello",
        "status": "published",
    }).execute()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/privacy/export",
            json={"format": "json"},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["format"] == "json"
    assert data["summary"]["posts"] == 1
    assert data["expires_at"] is not None


@pytest.mark.anyio()
async def test_request_deletion(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.delete(
            "/api/v1/privacy/me",
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["grace_period_days"] == 14
    assert data["scheduled_for"] is not None


@pytest.mark.anyio()
async def test_cancel_deletion(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    fake, key, user_id = authed_client
    # First request deletion
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        await client.delete(
            "/api/v1/privacy/me",
            headers={"X-API-Key": key},
        )
        # Re-activate key for cancel request (deletion deactivated it)
        for row in fake.tables["api_keys"]:
            row["is_active"] = True
        for row in fake.tables["users"]:
            if row["id"] == user_id:
                row["is_active"] = True

        resp = await client.post(
            "/api/v1/privacy/cancel-deletion",
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    assert resp.json()["cancelled"] is True


@pytest.mark.anyio()
async def test_restrict_processing(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    _fake, key, _uid = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/privacy/restrict",
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    assert resp.json()["restricted"] is True


@pytest.mark.anyio()
async def test_object_processing(
    authed_client: tuple[FakeSupabase, str, str],
) -> None:
    fake, key, user_id = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/privacy/object",
            json={"purposes": ["marketing", "analytics"]},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 200
    assert set(resp.json()["objected_purposes"]) == {"marketing", "analytics"}
    prefs = next(
        row
        for row in fake.tables["notification_preferences"]
        if row["user_id"] == user_id
    )
    assert prefs["product_updates"] is False
    assert prefs["monthly_summary"] is False
