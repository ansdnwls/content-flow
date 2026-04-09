"""Auth bypass tests — verify endpoints reject unauthenticated requests."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from tests.fakes import FakeSupabase

_PROTECTED_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/posts"),
    ("POST", "/api/v1/posts"),
    ("GET", "/api/v1/videos/templates"),
    ("POST", "/api/v1/videos/generate"),
    ("GET", "/api/v1/accounts"),
    ("GET", "/api/v1/webhooks/dead-letters"),
    ("GET", "/api/v1/keys"),
    ("POST", "/api/v1/keys"),
    ("GET", "/api/v1/billing/subscription"),
    ("POST", "/api/v1/billing/checkout"),
    ("GET", "/api/v1/usage"),
    ("GET", "/api/v1/onboarding/progress"),
    ("GET", "/api/v1/notifications/preferences"),
    ("POST", "/api/v1/auth/verify-email/request"),
    ("GET", "/api/v1/audit"),
]

_ADMIN_ROUTES: list[tuple[str, str]] = [
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/stats"),
    ("GET", "/api/v1/admin/jobs"),
]


@pytest.fixture()
def _fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    fake = FakeSupabase()
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    return fake


@pytest.mark.parametrize("method,path", _PROTECTED_ROUTES)
@pytest.mark.anyio()
async def test_no_key_returns_401(
    method: str,
    path: str,
    _fake_db: FakeSupabase,
) -> None:
    """Calling without X-API-Key must return 401."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.request(method, path)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", _PROTECTED_ROUTES)
@pytest.mark.anyio()
async def test_invalid_key_returns_401(
    method: str,
    path: str,
    _fake_db: FakeSupabase,
) -> None:
    """Calling with a bogus key must return 401."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.request(
            method, path, headers={"X-API-Key": "bogus_key_value"},
        )
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", _ADMIN_ROUTES)
@pytest.mark.anyio()
async def test_admin_no_key_returns_401(
    method: str,
    path: str,
    _fake_db: FakeSupabase,
) -> None:
    """Admin endpoints without X-Admin-Key must return 401."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.request(method, path)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", _ADMIN_ROUTES)
@pytest.mark.anyio()
async def test_admin_invalid_key_returns_401(
    method: str,
    path: str,
    _fake_db: FakeSupabase,
) -> None:
    """Admin endpoints with bogus X-Admin-Key must return 401."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.request(
            method, path, headers={"X-Admin-Key": "bogus_admin_key"},
        )
    assert resp.status_code == 401
