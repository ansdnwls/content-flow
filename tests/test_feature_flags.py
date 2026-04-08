from __future__ import annotations

from uuid import uuid4

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.core.feature_flags import (
    FeatureFlag,
    FeatureFlagNameConflictError,
    FeatureFlagStore,
)
from app.main import app
from tests.fakes import FakeSupabase


@pytest.fixture(autouse=True)
def clear_feature_flag_cache() -> None:
    FeatureFlagStore.clear_local_cache()


async def _fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def _setup_admin(fake: FakeSupabase, *, plan: str = "enterprise") -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row(
        "users",
        {
            "id": user_id,
            "email": "admin@test.com",
            "full_name": "Admin",
            "plan": plan,
            "is_active": True,
        },
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="admin", prefix="cf_admin")
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


async def test_boolean_flag_enabled_and_disabled() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)
    await store.create_flag(FeatureFlag(name="boolean_flag", type="boolean", enabled=True))

    assert await store.is_enabled("boolean_flag") is True

    await store.update_flag("boolean_flag", {"enabled": False})
    assert await store.is_enabled("boolean_flag") is False


async def test_percentage_flag_is_deterministic_for_same_user() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)
    await store.create_flag(
        FeatureFlag(name="percent_flag", type="percentage", percentage=37),
    )

    results = [await store.is_enabled("percent_flag", user_id="same-user") for _ in range(5)]

    assert results == [results[0]] * 5


async def test_percentage_flag_without_user_uses_default_fallback() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)
    await store.create_flag(
        FeatureFlag(
            name="percent_default_on",
            type="percentage",
            percentage=50,
            default_enabled=True,
        ),
    )

    assert await store.is_enabled("percent_default_on") is True


async def test_user_list_flag_includes_listed_user() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)
    await store.create_flag(
        FeatureFlag(name="invite_only", type="user_list", user_ids=["user-1", "user-2"]),
    )

    assert await store.is_enabled("invite_only", user_id="user-2") is True


async def test_user_list_flag_excludes_unlisted_user() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)
    await store.create_flag(
        FeatureFlag(name="invite_only", type="user_list", user_ids=["user-1"]),
    )

    assert await store.is_enabled("invite_only", user_id="user-9") is False


async def test_plan_based_flag_respects_free_build_scale_threshold() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)
    await store.create_flag(
        FeatureFlag(name="premium_feature", type="plan_based", required_plan="scale"),
    )

    assert await store.is_enabled("premium_feature", context={"plan": "free"}) is False
    assert await store.is_enabled("premium_feature", context={"plan": "build"}) is False
    assert await store.is_enabled("premium_feature", context={"plan": "scale"}) is True
    assert await store.is_enabled("premium_feature", context={"plan": "enterprise"}) is True


async def test_missing_flag_returns_default_fallback() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)

    assert await store.is_enabled("new_sorting", user_id="missing-user") is False


async def test_redis_failure_uses_defaults_gracefully() -> None:
    class BrokenRedis:
        async def get(self, key: str) -> str | None:
            raise RuntimeError(key)

    store = FeatureFlagStore(BrokenRedis())

    assert await store.is_enabled(
        "ytboost_ai_thumbnails",
        user_id="scale-user",
        context={"plan": "scale"},
    )


async def test_admin_feature_flag_crud_and_evaluate(monkeypatch) -> None:
    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake)
    redis = await _fake_redis()

    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.admin.get_supabase", lambda: fake)
    monkeypatch.setattr(app.state, "redis", redis, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        list_resp = await client.get("/api/v1/admin/feature-flags")
        assert list_resp.status_code == 200
        assert any(item["name"] == "new_dashboard_ui" for item in list_resp.json()["data"])

        create_resp = await client.post(
            "/api/v1/admin/feature-flags",
            json={"name": "custom_beta", "type": "boolean", "enabled": True},
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["enabled"] is True

        patch_resp = await client.patch(
            "/api/v1/admin/feature-flags/custom_beta",
            json={"enabled": False},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["enabled"] is False

        eval_resp = await client.post(
            "/api/v1/admin/feature-flags/custom_beta/evaluate",
            json={"user_id": "user-1", "context": {"plan": "scale"}},
        )
        assert eval_resp.status_code == 200
        assert eval_resp.json()["enabled"] is False

        delete_resp = await client.delete("/api/v1/admin/feature-flags/custom_beta")
        assert delete_resp.status_code == 200
        assert delete_resp.json() is None


async def test_non_enterprise_admin_cannot_manage_feature_flags(monkeypatch) -> None:
    fake = FakeSupabase()
    _, admin_key = _setup_admin(fake, plan="build")
    redis = await _fake_redis()

    monkeypatch.setattr("app.core.admin_auth.get_supabase", lambda: fake)
    monkeypatch.setattr(app.state, "redis", redis, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-Admin-Key": admin_key},
    ) as client:
        response = await client.get("/api/v1/admin/feature-flags")

    assert response.status_code == 403


async def test_cache_invalidation_after_update() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)
    await store.create_flag(FeatureFlag(name="cached_flag", type="boolean", enabled=True))

    assert await store.is_enabled("cached_flag") is True

    await store.update_flag("cached_flag", {"enabled": False})
    assert await store.is_enabled("cached_flag") is False


async def test_create_feature_flag_rejects_name_conflict() -> None:
    redis = await _fake_redis()
    store = FeatureFlagStore(redis)

    with pytest.raises(FeatureFlagNameConflictError) as exc_info:
        await store.create_flag(FeatureFlag(name="new_dashboard_ui", type="boolean", enabled=True))

    assert "new_dashboard_ui" in str(exc_info.value)
