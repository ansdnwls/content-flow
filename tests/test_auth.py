from uuid import uuid4

import fakeredis.aioredis
from starlette.requests import Request

from app.api.deps import get_current_user
from app.core.admin_auth import get_admin_user
from app.core.auth import build_api_key_record, issue_api_key, verify_api_key
from tests.fakes import FakeSupabase


def test_issue_api_key_uses_contentflow_prefix() -> None:
    issued = issue_api_key()

    assert issued.raw_key.startswith("cf_live_")
    assert issued.preview.startswith("cf_live_...")
    assert verify_api_key(issued.raw_key, issued.hashed_key) is True


def test_build_api_key_record_returns_insertable_payload() -> None:
    user_id = uuid4()

    issued, record = build_api_key_record(user_id=user_id, name="default")

    assert record["user_id"] == str(user_id)
    assert record["name"] == "default"
    assert record["hashed_key"] == issued.hashed_key
    assert record["is_active"] is True


def _make_request(redis) -> Request:
    app = type("TestApp", (), {})()
    app.state = type("State", (), {})()
    app.state.redis = redis
    return Request({"type": "http", "headers": [], "app": app, "state": {}})


async def test_get_current_user_caches_verified_api_key(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users",
        {"id": user_id, "email": "cache@test.com", "plan": "build"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    verify_calls = {"count": 0}

    def counting_verify(raw_key: str, hashed_key: str) -> bool:
        verify_calls["count"] += 1
        return verify_api_key(raw_key, hashed_key)

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr("app.api.deps.verify_api_key", counting_verify)
    monkeypatch.setattr(
        "app.api.deps.resolve_workspace_id_for_user",
        lambda *args, **kwargs: None,
    )

    first = await get_current_user(_make_request(redis), api_key=issued.raw_key)
    second = await get_current_user(_make_request(redis), api_key=issued.raw_key)

    assert first.id == user_id
    assert second.id == user_id
    assert verify_calls["count"] == 1


async def test_get_admin_user_caches_verified_admin_key(monkeypatch) -> None:
    fake_supabase = FakeSupabase()
    user_id = str(uuid4())
    fake_supabase.insert_row(
        "users",
        {"id": user_id, "email": "admin-cache@test.com", "plan": "enterprise"},
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="admin", prefix="cf_admin")
    record["user_id"] = user_id
    fake_supabase.insert_row("api_keys", record)

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    verify_calls = {"count": 0}

    def counting_verify(raw_key: str, hashed_key: str) -> bool:
        verify_calls["count"] += 1
        return verify_api_key(raw_key, hashed_key)

    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake_supabase)
    monkeypatch.setattr("app.core.admin_auth.verify_api_key", counting_verify)

    first = await get_admin_user(_make_request(redis), admin_key=issued.raw_key)
    second = await get_admin_user(_make_request(redis), admin_key=issued.raw_key)

    assert first["id"] == user_id
    assert second["id"] == user_id
    assert verify_calls["count"] == 1
