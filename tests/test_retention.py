"""Data retention service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.retention_service import (
    RETENTION_DAYS,
    process_pending_deletions,
    purge_expired_data,
)
from tests.fakes import FakeSupabase


@pytest.fixture()
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    fake = FakeSupabase()
    monkeypatch.setattr(
        "app.services.retention_service.get_supabase", lambda: fake,
    )
    return fake


def _old_timestamp(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days + 1)).isoformat()


def test_purge_expired_audit_logs(fake_db: FakeSupabase) -> None:
    old = _old_timestamp(RETENTION_DAYS["audit_logs"])
    fake_db.table("audit_logs").insert({
        "user_id": "u1",
        "action": "test",
        "resource": "test",
        "created_at": old,
    }).execute()
    fake_db.table("audit_logs").insert({
        "user_id": "u2",
        "action": "recent",
        "resource": "test",
    }).execute()

    results = purge_expired_data()
    assert results["audit_logs"] == 1
    assert len(fake_db.tables["audit_logs"]) == 1


def test_purge_expired_email_logs(fake_db: FakeSupabase) -> None:
    old = _old_timestamp(RETENTION_DAYS["email_logs"])
    fake_db.table("email_logs").insert({
        "user_id": "u1",
        "to_email": "a@b.com",
        "subject": "old",
        "created_at": old,
    }).execute()

    results = purge_expired_data()
    assert results["email_logs"] == 1


def test_purge_keeps_fresh_data(fake_db: FakeSupabase) -> None:
    fake_db.table("audit_logs").insert({
        "user_id": "u1",
        "action": "fresh",
        "resource": "test",
    }).execute()

    results = purge_expired_data()
    assert results["audit_logs"] == 0
    assert len(fake_db.tables["audit_logs"]) == 1


def test_process_pending_deletions(fake_db: FakeSupabase) -> None:
    user_id = "user-to-delete"
    fake_db.table("users").insert({
        "id": user_id,
        "email": "del@test.com",
        "plan": "free",
        "is_active": False,
    }).execute()
    fake_db.table("posts").insert({
        "owner_id": user_id,
        "text": "my post",
        "status": "published",
    }).execute()
    fake_db.table("consents").insert({
        "user_id": user_id,
        "purpose": "analytics",
        "granted": True,
    }).execute()

    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    fake_db.table("deletion_requests").insert({
        "user_id": user_id,
        "status": "pending",
        "scheduled_for": past,
        "requested_at": past,
    }).execute()

    processed = process_pending_deletions()
    assert len(processed) == 1
    assert processed[0]["status"] == "completed"

    # User should be anonymized but preserved for FK-linked compliance records.
    assert len(fake_db.tables["users"]) == 1
    assert fake_db.tables["users"][0]["email"].startswith("deleted+")
    assert fake_db.tables["users"][0]["subscription_status"] == "deleted_gdpr"
    # Consents should be deleted
    assert len(fake_db.tables["consents"]) == 0
    assert fake_db.tables["posts"][0]["status"] == "deleted_gdpr"
    assert fake_db.tables["posts"][0]["text"] is None


def test_process_skips_future_deletions(fake_db: FakeSupabase) -> None:
    user_id = "future-user"
    fake_db.table("users").insert({
        "id": user_id,
        "email": "future@test.com",
        "plan": "free",
        "is_active": False,
    }).execute()

    future = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    fake_db.table("deletion_requests").insert({
        "user_id": user_id,
        "status": "pending",
        "scheduled_for": future,
        "requested_at": datetime.now(UTC).isoformat(),
    }).execute()

    processed = process_pending_deletions()
    assert len(processed) == 0
    assert len(fake_db.tables["users"]) == 1
