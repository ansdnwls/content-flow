"""Integration tests for API key management: create, list, rotate, per-key audit."""

from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase

KEYS_URL = "/api/v1/keys"


def _setup(monkeypatch):
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    fake_sb.insert_row(
        "users",
        {"id": user_id, "email": "keys@example.com", "plan": "build"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="auth")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    def fake_get_supabase():
        return fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.api_keys.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.core.audit.get_supabase", fake_get_supabase)

    return fake_sb, user_id, issued.raw_key


async def test_create_key(monkeypatch) -> None:
    """POST /keys creates a new key and returns raw_key once."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            KEYS_URL,
            json={"name": "ci-deploy", "expires_in": "90d"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "ci-deploy"
    assert "raw_key" in body
    assert body["raw_key"].startswith("cf_")
    assert body["is_active"] is True
    assert body["expires_at"] is not None


async def test_create_key_never_expires(monkeypatch) -> None:
    """Key with expires_in='never' has no expires_at."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(
            KEYS_URL,
            json={"name": "permanent", "expires_in": "never"},
        )

    assert resp.status_code == 201
    assert resp.json()["expires_at"] is None


async def test_list_keys(monkeypatch) -> None:
    """GET /keys returns all keys for the user."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        # Create an extra key
        await client.post(KEYS_URL, json={"name": "extra"})
        resp = await client.get(KEYS_URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert all("raw_key" not in k for k in body["data"])


async def test_rotate_key(monkeypatch) -> None:
    """POST /keys/{id}/rotate issues new key and schedules old one."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        # Create a key to rotate
        create_resp = await client.post(KEYS_URL, json={"name": "rotate-me"})
        key_id = create_resp.json()["id"]

        resp = await client.post(f"{KEYS_URL}/{key_id}/rotate")

    assert resp.status_code == 200
    body = resp.json()
    assert body["old_key_id"] == key_id
    assert body["new_key"]["rotated_from"] == key_id
    assert "raw_key" in body["new_key"]
    assert body["old_key_deactivates_at"] is not None


async def test_rotate_nonexistent_key_404(monkeypatch) -> None:
    """Rotating a non-existent key returns 404."""
    _fake_sb, _user_id, raw_key = _setup(monkeypatch)
    fake_id = str(uuid4())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.post(f"{KEYS_URL}/{fake_id}/rotate")

    assert resp.status_code == 404


async def test_key_audit_log(monkeypatch) -> None:
    """GET /keys/{id}/audit returns audit entries for that key."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    # Seed an audit entry for a known key
    existing_keys = fake_sb.tables["api_keys"]
    key_id = existing_keys[0]["id"]
    fake_sb.insert_row("audit_logs", {
        "user_id": user_id,
        "api_key_id": key_id,
        "action": "key.created",
        "resource": f"api_keys/{key_id}",
        "metadata": {},
    })

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(f"{KEYS_URL}/{key_id}/audit")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert body["data"][0]["action"] == "key.created"
