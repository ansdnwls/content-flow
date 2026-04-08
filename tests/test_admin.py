"""Tests for Admin Panel API."""

from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


def _setup_admin(fake: FakeSupabase) -> tuple[str, str]:
    """Create an enterprise user with an admin API key."""
    user_id = str(uuid4())
    fake.insert_row("users", {
        "id": user_id, "email": "admin@test.com",
        "full_name": "Admin", "plan": "enterprise", "is_active": True,
    })
    issued, rec = build_api_key_record(user_id=uuid4(), name="admin", prefix="cf_admin")
    rec["user_id"] = user_id
    fake.insert_row("api_keys", rec)
    return user_id, issued.raw_key


def _setup_regular_user(
    fake: FakeSupabase, email: str = "user@test.com", plan: str = "free",
) -> str:
    user_id = str(uuid4())
    fake.insert_row("users", {
        "id": user_id, "email": email,
        "full_name": "Regular", "plan": plan, "is_active": True,
    })
    return user_id


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


async def test_admin_requires_key(monkeypatch) -> None:
    fake = FakeSupabase()
    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401


async def test_admin_rejects_non_enterprise(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id = str(uuid4())
    fake.insert_row("users", {
        "id": user_id, "email": "build@test.com", "plan": "build", "is_active": True,
    })
    issued, rec = build_api_key_record(user_id=uuid4(), name="admin", prefix="cf_admin")
    rec["user_id"] = user_id
    fake.insert_row("api_keys", rec)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": issued.raw_key},
    ) as client:
        resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


async def test_list_users(monkeypatch) -> None:
    fake = FakeSupabase()
    admin_id, admin_key = _setup_admin(fake)
    _setup_regular_user(fake, "a@t.com", "free")
    _setup_regular_user(fake, "b@t.com", "build")

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.get("/api/v1/admin/users")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3  # admin + 2 users


async def test_get_user_detail(monkeypatch) -> None:
    fake = FakeSupabase()
    admin_id, admin_key = _setup_admin(fake)
    user_id = _setup_regular_user(fake, "detail@t.com", "build")
    fake.insert_row("posts", {"id": str(uuid4()), "owner_id": user_id, "status": "published"})
    fake.insert_row("video_jobs", {
        "id": str(uuid4()), "owner_id": user_id,
        "topic": "t", "mode": "general", "status": "done",
    })

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.get(f"/api/v1/admin/users/{user_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "detail@t.com"
    assert body["posts_count"] == 1
    assert body["videos_count"] == 1


async def test_get_user_not_found(monkeypatch) -> None:
    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.get(f"/api/v1/admin/users/{uuid4()}")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Plan change
# ---------------------------------------------------------------------------


async def test_change_plan(monkeypatch) -> None:
    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    user_id = _setup_regular_user(fake, "plan@t.com", "free")

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.post(
            f"/api/v1/admin/users/{user_id}/plan",
            json={"plan": "scale"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["previous_plan"] == "free"
    assert body["new_plan"] == "scale"


# ---------------------------------------------------------------------------
# Suspend
# ---------------------------------------------------------------------------


async def test_suspend_user(monkeypatch) -> None:
    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    user_id = _setup_regular_user(fake, "sus@t.com", "build")
    issued, rec = build_api_key_record(user_id=uuid4(), name="default")
    rec["user_id"] = user_id
    fake.insert_row("api_keys", rec)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.post(
            f"/api/v1/admin/users/{user_id}/suspend",
            json={"reason": "TOS violation"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "suspended"

    # User should be deactivated
    user_row = next(r for r in fake.tables["users"] if r["id"] == user_id)
    assert user_row["is_active"] is False


# ---------------------------------------------------------------------------
# System stats
# ---------------------------------------------------------------------------


async def test_system_stats(monkeypatch) -> None:
    fake = FakeSupabase()
    admin_id, admin_key = _setup_admin(fake)
    _setup_regular_user(fake, "s1@t.com", "free")
    _setup_regular_user(fake, "s2@t.com", "build")
    fake.insert_row("posts", {"id": str(uuid4()), "owner_id": admin_id, "status": "published"})

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.get("/api/v1/admin/stats")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] == 3
    assert body["total_posts"] == 1
    assert "enterprise" in body["plans"]


# ---------------------------------------------------------------------------
# Admin auth unit tests
# ---------------------------------------------------------------------------


async def test_admin_auth_rejects_regular_api_key(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id = str(uuid4())
    fake.insert_row("users", {
        "id": user_id, "email": "reg@t.com", "plan": "enterprise", "is_active": True,
    })
    issued, rec = build_api_key_record(user_id=uuid4(), name="default")
    rec["user_id"] = user_id
    fake.insert_row("api_keys", rec)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": issued.raw_key},
    ) as client:
        resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Compliance dashboard
# ---------------------------------------------------------------------------


async def test_compliance_dashboard(monkeypatch) -> None:
    fake = FakeSupabase()
    admin_id, admin_key = _setup_admin(fake)
    user_id = _setup_regular_user(fake, "privacy@t.com", "build")

    fake.insert_row("consents", {
        "user_id": user_id,
        "purpose": "marketing",
        "granted": True,
    })
    fake.insert_row("deletion_requests", {
        "user_id": user_id,
        "status": "pending",
        "scheduled_for": "2026-04-20T00:00:00+00:00",
    })
    fake.insert_row("deletion_requests", {
        "user_id": admin_id,
        "status": "completed",
        "scheduled_for": "2026-04-01T00:00:00+00:00",
    })
    fake.insert_row("data_breaches", {"severity": "low"})
    fake.insert_row("dpa_signatures", {
        "user_id": admin_id,
        "dpa_version": "2026-04",
        "signer_name": "Admin",
        "signer_email": "admin@test.com",
        "company": "ContentFlow",
    })
    fake.insert_row("audit_logs", {
        "user_id": user_id,
        "action": "privacy.export_request",
        "resource": "privacy",
    })

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.get("/api/v1/admin/compliance/dashboard")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] == 2
    assert body["consented_users"] == 1
    assert body["pending_deletions"] == 1
    assert body["completed_deletions"] == 1
    assert body["export_requests_this_month"] == 1
    assert body["recent_breaches"] == 1
    assert body["dpa_signed_count"] == 1


async def test_pending_deletions(monkeypatch) -> None:
    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    user_1 = _setup_regular_user(fake, "delete1@t.com", "build")
    user_2 = _setup_regular_user(fake, "delete2@t.com", "scale")

    fake.insert_row("deletion_requests", {
        "user_id": user_2,
        "status": "pending",
        "requested_at": "2026-04-02T00:00:00+00:00",
        "scheduled_for": "2026-04-18T00:00:00+00:00",
    })
    fake.insert_row("deletion_requests", {
        "user_id": user_1,
        "status": "pending",
        "requested_at": "2026-04-01T00:00:00+00:00",
        "scheduled_for": "2026-04-12T00:00:00+00:00",
    })
    fake.insert_row("deletion_requests", {
        "user_id": user_1,
        "status": "completed",
        "requested_at": "2026-03-20T00:00:00+00:00",
        "scheduled_for": "2026-04-03T00:00:00+00:00",
    })

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.get("/api/v1/admin/compliance/pending-deletions")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["user_id"] for item in body["pending"]] == [user_1, user_2]


async def test_compliance_data_requests(monkeypatch) -> None:
    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    user_id = _setup_regular_user(fake, "requester@t.com", "build")

    fake.insert_row("audit_logs", {
        "user_id": user_id,
        "action": "privacy.export_request",
        "resource": "privacy",
        "created_at": "2026-04-02T08:00:00+00:00",
        "metadata": {"format": "json"},
    })
    fake.insert_row("audit_logs", {
        "user_id": user_id,
        "action": "auth.login",
        "resource": "auth",
        "created_at": "2026-04-02T09:00:00+00:00",
    })
    fake.insert_row("audit_logs", {
        "user_id": user_id,
        "action": "privacy.deletion_request",
        "resource": "privacy",
        "created_at": "2026-04-03T10:00:00+00:00",
    })

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        resp = await client.get("/api/v1/admin/compliance/data-requests?limit=2")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["action"] for item in body["requests"]] == [
        "privacy.deletion_request",
        "privacy.export_request",
    ]
    assert body["requests"][1]["metadata"] == {"format": "json"}
