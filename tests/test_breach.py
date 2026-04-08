"""Data breach notification service tests."""

from __future__ import annotations

import pytest

from app.services.breach_notification import (
    list_breaches,
    notify_affected_users,
    notify_authority,
    report_breach,
    resolve_breach,
)
from tests.fakes import FakeSupabase


@pytest.fixture()
def fake_db(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    fake = FakeSupabase()
    monkeypatch.setattr(
        "app.services.breach_notification.get_supabase", lambda: fake,
    )
    return fake


def test_report_breach(fake_db: FakeSupabase) -> None:
    result = report_breach(
        severity="high",
        affected_user_count=100,
        description="Token leak",
    )
    assert result["severity"] == "high"
    assert result["affected_user_count"] == 100
    assert result["authority_notification_deadline_hours"] == 72
    assert len(result["incident_response_checklist"]) >= 3
    assert len(fake_db.tables["data_breaches"]) == 1


def test_notify_affected_users(fake_db: FakeSupabase) -> None:
    breach = report_breach(
        severity="critical",
        affected_user_count=50,
        description="DB exposed",
    )
    count = notify_affected_users(breach["id"])
    assert count == 50

    updated = fake_db.tables["data_breaches"][0]
    assert updated["status"] == "users_notified"
    assert updated["notified_users_at"] is not None


def test_notify_authority(fake_db: FakeSupabase) -> None:
    breach = report_breach(
        severity="high",
        affected_user_count=200,
        description="Unauthorized access",
    )
    template = notify_authority(breach["id"])
    assert template["breach_id"] == breach["id"]
    assert template["template"] == "supervisory_authority_notification"
    assert template["deadline_hours"] == 72

    updated = fake_db.tables["data_breaches"][0]
    assert updated["status"] == "authority_notified"


def test_report_breach_rejects_invalid_severity(fake_db: FakeSupabase) -> None:
    with pytest.raises(ValueError):
        report_breach(
            severity="urgent",
            affected_user_count=1,
            description="Bad severity",
        )


def test_resolve_breach(fake_db: FakeSupabase) -> None:
    breach = report_breach(
        severity="medium",
        affected_user_count=10,
        description="Minor leak",
    )
    assert resolve_breach(breach["id"]) is True

    updated = fake_db.tables["data_breaches"][0]
    assert updated["status"] == "resolved"
    assert updated["resolved_at"] is not None


def test_list_breaches(fake_db: FakeSupabase) -> None:
    report_breach(severity="low", affected_user_count=5, description="A")
    report_breach(severity="high", affected_user_count=50, description="B")

    all_breaches = list_breaches()
    assert len(all_breaches) == 2


def test_list_breaches_by_status(fake_db: FakeSupabase) -> None:
    breach = report_breach(
        severity="high", affected_user_count=10, description="X",
    )
    resolve_breach(breach["id"])
    report_breach(severity="low", affected_user_count=1, description="Y")

    resolved = list_breaches(status="resolved")
    assert len(resolved) == 1
    assert resolved[0]["severity"] == "high"
