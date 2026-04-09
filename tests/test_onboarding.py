"""Tests for onboarding flow — service + API endpoints."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedUser
from app.main import app
from app.services.onboarding_service import (
    STEP_IDS,
    STEPS,
    complete_step,
    get_next_action,
    get_progress,
    init_progress,
    skip_remaining,
)
from tests.fakes import FakeSupabase

_USER = AuthenticatedUser(
    id="user-ob",
    email="onboard@example.com",
    plan="build",
    is_test_key=False,
    workspace_id="ws-1",
)


@pytest.fixture()
def fake_sb():
    return FakeSupabase()


def _patch_sb(fake_sb: FakeSupabase):
    """Patch get_supabase at all import locations used by onboarding."""
    stack = ExitStack()
    stack.enter_context(patch("app.core.db.get_supabase", return_value=fake_sb))
    stack.enter_context(
        patch("app.services.onboarding_service.get_supabase", return_value=fake_sb),
    )
    stack.enter_context(
        patch("app.services.notification_service.get_supabase", return_value=fake_sb),
    )
    return stack


def _client(fake_sb: FakeSupabase) -> TestClient:
    from app.api.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _USER
    return TestClient(app)


def _cleanup():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unit tests — service layer
# ---------------------------------------------------------------------------


# 1. init_progress creates welcome step
def test_init_progress(fake_sb):
    with _patch_sb(fake_sb):
        result = init_progress("user-ob")
    assert len(result) == 1
    assert result[0]["step"] == "welcome"
    assert result[0]["completed_at"] is not None


# 2. init_progress is idempotent
def test_init_progress_idempotent(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        init_progress("user-ob")
    assert len(fake_sb.tables["onboarding_progress"]) == 1


# 3. get_progress returns all steps
def test_get_progress_all_steps(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        progress = get_progress("user-ob")
    assert progress["total_steps"] == len(STEPS)
    assert progress["completed_count"] == 1  # welcome only
    assert not progress["all_complete"]
    step_ids = [s["id"] for s in progress["steps"]]
    assert step_ids == [s.id for s in STEPS]


# 4. complete_step marks step done
def test_complete_step(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        progress = complete_step("user-ob", "verify_email")
    verify = next(s for s in progress["steps"] if s["id"] == "verify_email")
    assert verify["completed"] is True
    assert progress["completed_count"] == 2


# 5. complete_step with invalid step raises ValueError
def test_complete_step_invalid(fake_sb):
    with _patch_sb(fake_sb), pytest.raises(ValueError, match="Unknown"):
        complete_step("user-ob", "nonexistent_step")


# 6. complete_step is idempotent
def test_complete_step_idempotent(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        complete_step("user-ob", "verify_email")
        progress = complete_step("user-ob", "verify_email")
    assert progress["completed_count"] == 2
    verify_rows = [
        r for r in fake_sb.tables["onboarding_progress"]
        if r["step"] == "verify_email"
    ]
    assert len(verify_rows) == 1


# 7. skip_remaining marks all incomplete as done
def test_skip_remaining(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        complete_step("user-ob", "verify_email")
        # Insert user row for the update triggered by all_complete
        fake_sb.table("users").insert(
            {"id": "user-ob", "onboarding_completed": False},
        ).execute()
        progress = skip_remaining("user-ob")
    assert progress["all_complete"] is True
    assert progress["completed_count"] == len(STEPS)
    skipped = [
        r for r in fake_sb.tables["onboarding_progress"]
        if r.get("data", {}).get("skipped")
    ]
    assert len(skipped) == len(STEPS) - 2  # welcome + verify_email already done


# 8. get_next_action returns first incomplete step
def test_get_next_action(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        result = get_next_action("user-ob")
    assert result is not None
    assert result["step"] == "verify_email"
    assert "hints" in result


# 9. get_next_action returns None when all complete
def test_get_next_action_all_done(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        # Insert user row for the update triggered by all_complete
        fake_sb.table("users").insert(
            {"id": "user-ob", "onboarding_completed": False},
        ).execute()
        skip_remaining("user-ob")
        result = get_next_action("user-ob")
    assert result is None


# 10. All steps complete triggers notification + user update
def test_all_complete_triggers_notification(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        fake_sb.table("users").insert(
            {"id": "user-ob", "onboarding_completed": False},
        ).execute()

        for step_def in STEPS:
            if step_def.id != "welcome":
                complete_step("user-ob", step_def.id)

    notifications = [
        n for n in fake_sb.tables["notifications"]
        if n["user_id"] == "user-ob" and n["type"] == "onboarding_complete"
    ]
    assert len(notifications) == 1
    assert "complete" in notifications[0]["title"].lower()

    user = next(r for r in fake_sb.tables["users"] if r["id"] == "user-ob")
    assert user["onboarding_completed"] is True


# ---------------------------------------------------------------------------
# Integration tests — API endpoints
# ---------------------------------------------------------------------------


# 11. GET /progress returns step list
def test_api_get_progress(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        c = _client(fake_sb)
        resp = c.get("/api/v1/onboarding/progress")
    _cleanup()
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_steps"] == len(STEPS)
    assert isinstance(body["steps"], list)


# 12. POST /steps/{step}/complete
def test_api_complete_step(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        c = _client(fake_sb)
        resp = c.post(
            "/api/v1/onboarding/steps/verify_email/complete",
            json={"data": {"method": "link"}},
        )
    _cleanup()
    assert resp.status_code == 200
    body = resp.json()
    verify = next(s for s in body["steps"] if s["id"] == "verify_email")
    assert verify["completed"] is True


# 13. POST /steps/{step}/complete with invalid step → 422
def test_api_complete_invalid_step(fake_sb):
    with _patch_sb(fake_sb):
        c = _client(fake_sb)
        resp = c.post("/api/v1/onboarding/steps/bogus/complete")
    _cleanup()
    assert resp.status_code == 422


# 14. POST /skip marks all done
def test_api_skip(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        fake_sb.table("users").insert(
            {"id": "user-ob", "onboarding_completed": False},
        ).execute()
        c = _client(fake_sb)
        resp = c.post("/api/v1/onboarding/skip")
    _cleanup()
    assert resp.status_code == 200
    assert resp.json()["all_complete"] is True


# 15. GET /next-action returns hint
def test_api_next_action(fake_sb):
    with _patch_sb(fake_sb):
        init_progress("user-ob")
        c = _client(fake_sb)
        resp = c.get("/api/v1/onboarding/next-action")
    _cleanup()
    assert resp.status_code == 200
    body = resp.json()
    assert body["step"] == "verify_email"
    assert "hints" in body


# 16. STEP_IDS matches STEPS definitions
def test_step_ids_consistent():
    assert STEP_IDS == {s.id for s in STEPS}
    assert len(STEP_IDS) == 6
