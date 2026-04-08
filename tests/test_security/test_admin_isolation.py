"""Admin isolation tests — regular API keys cannot access admin endpoints."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


@pytest.fixture()
def regular_key_setup(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeSupabase, str]:
    """Create a regular user with a cf_live key (NOT admin)."""
    fake = FakeSupabase()
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)

    user_id = str(uuid4())
    fake.table("users").insert({
        "id": user_id,
        "email": "user@test.com",
        "plan": "build",
        "is_active": True,
    }).execute()

    issued, record = build_api_key_record(
        user_id=uuid4(), name="test-key",
    )
    record["user_id"] = user_id
    fake.table("api_keys").insert(record).execute()

    return fake, issued.raw_key


@pytest.mark.anyio()
async def test_regular_key_cannot_access_admin_users(
    regular_key_setup: tuple[FakeSupabase, str],
) -> None:
    _fake, raw_key = regular_key_setup
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"X-Admin-Key": raw_key},
        )
    assert resp.status_code == 401


@pytest.mark.anyio()
async def test_regular_key_cannot_access_admin_stats(
    regular_key_setup: tuple[FakeSupabase, str],
) -> None:
    _fake, raw_key = regular_key_setup
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/api/v1/admin/stats",
            headers={"X-Admin-Key": raw_key},
        )
    assert resp.status_code == 401


@pytest.mark.anyio()
async def test_non_enterprise_admin_key_returns_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An admin-prefixed key for a non-enterprise user must return 403."""
    fake = FakeSupabase()
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)

    user_id = str(uuid4())
    fake.table("users").insert({
        "id": user_id,
        "email": "admin@test.com",
        "plan": "build",  # NOT enterprise
        "is_active": True,
    }).execute()

    issued, record = build_api_key_record(
        user_id=uuid4(), name="admin-key", prefix="cf_admin",
    )
    record["user_id"] = user_id
    fake.table("api_keys").insert(record).execute()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/api/v1/admin/users",
            headers={"X-Admin-Key": issued.raw_key},
        )
    assert resp.status_code == 403
