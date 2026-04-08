"""Tests for audit log query endpoint and audit core module."""

from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.audit import flush_audit_logs, mask_sensitive, record_audit, reset_audit_writer
from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase

AUDIT_URL = "/api/v1/audit"


def _setup(monkeypatch):
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    fake_sb.insert_row(
        "users",
        {"id": user_id, "email": "audit@example.com", "plan": "build"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="audit-key")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    def fake_get_supabase():
        return fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.v1.audit.get_supabase", fake_get_supabase)

    return fake_sb, user_id, issued.raw_key


def test_mask_sensitive_hides_tokens() -> None:
    """mask_sensitive replaces sensitive fields with '***'."""
    data = {
        "username": "alice",
        "access_token": "secret123",
        "password": "hunter2",
        "nested": {"refresh_token": "r_tok", "safe": "ok"},
    }
    masked = mask_sensitive(data)
    assert masked["username"] == "alice"
    assert masked["access_token"] == "***"
    assert masked["password"] == "***"
    assert masked["nested"]["refresh_token"] == "***"
    assert masked["nested"]["safe"] == "ok"


def test_mask_sensitive_no_mutation() -> None:
    """Original dict is not mutated."""
    data = {"token": "abc"}
    masked = mask_sensitive(data)
    assert masked["token"] == "***"
    assert data["token"] == "abc"


async def test_list_audit_logs(monkeypatch) -> None:
    """GET /audit returns paginated audit logs for the user."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    for i in range(3):
        fake_sb.insert_row("audit_logs", {
            "user_id": user_id,
            "action": "key.created",
            "resource": f"api_keys/key-{i}",
            "metadata": {},
        })

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(AUDIT_URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["data"]) == 3


async def test_list_audit_logs_filter_action(monkeypatch) -> None:
    """Action filter returns only matching entries."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    fake_sb.insert_row("audit_logs", {
        "user_id": user_id,
        "action": "key.created",
        "resource": "api_keys/k1",
        "metadata": {},
    })
    fake_sb.insert_row("audit_logs", {
        "user_id": user_id,
        "action": "key.rotated",
        "resource": "api_keys/k2",
        "metadata": {},
    })

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(AUDIT_URL, params={"action": "key.rotated"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["action"] == "key.rotated"


async def test_list_audit_logs_pagination(monkeypatch) -> None:
    """Pagination returns correct page of results."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    for i in range(5):
        fake_sb.insert_row("audit_logs", {
            "user_id": user_id,
            "action": "api.call",
            "resource": f"posts/{i}",
            "metadata": {},
        })

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(AUDIT_URL, params={"page": 1, "limit": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["data"]) == 2
    assert body["page"] == 1
    assert body["limit"] == 2


async def test_audit_logs_isolation(monkeypatch) -> None:
    """Users only see their own audit logs."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    other_user_id = str(uuid4())

    fake_sb.insert_row("audit_logs", {
        "user_id": user_id,
        "action": "mine",
        "resource": "r1",
        "metadata": {},
    })
    fake_sb.insert_row("audit_logs", {
        "user_id": other_user_id,
        "action": "theirs",
        "resource": "r2",
        "metadata": {},
    })

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(AUDIT_URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["action"] == "mine"


async def test_record_audit_uses_batch_flush(monkeypatch) -> None:
    await reset_audit_writer()
    fake_sb = FakeSupabase()
    monkeypatch.setattr("app.core.audit.get_supabase", lambda: fake_sb)

    await record_audit(
        user_id=str(uuid4()),
        action="privacy.access",
        resource="privacy",
        metadata={"token": "secret"},
    )
    assert len(fake_sb.tables["audit_logs"]) == 0

    flushed = await flush_audit_logs()
    assert flushed == 1
    assert len(fake_sb.tables["audit_logs"]) == 1
    assert fake_sb.tables["audit_logs"][0]["metadata"]["token"] == "***"

    await reset_audit_writer()
