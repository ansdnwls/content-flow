from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


def _patch_supabase(monkeypatch, fake: FakeSupabase) -> None:
    targets = [
        "app.api.deps.get_supabase",
        "app.api.v1.api_keys.get_supabase",
        "app.api.v1.domains.get_supabase",
        "app.api.v1.posts.get_supabase",
        "app.api.v1.usage.get_supabase",
        "app.api.v1.workspaces.get_supabase",
        "app.core.billing.get_supabase",
        "app.core.branding.get_supabase",
        "app.core.workspaces.get_supabase",
        "app.middleware.custom_domain.get_supabase",
    ]
    for target in targets:
        monkeypatch.setattr(target, lambda: fake, raising=False)


def _setup_auth(fake: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row(
        "users",
        {
            "id": user_id,
            "email": "owner@example.com",
            "plan": "build",
            "default_workspace_id": None,
        },
    )
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


async def test_workspace_crud_branding_and_domain(monkeypatch) -> None:
    fake = FakeSupabase()
    _user_id, raw_key = _setup_auth(fake)
    _patch_supabase(monkeypatch, fake)
    monkeypatch.setattr("app.api.v1.domains.verify_custom_domain_record", lambda _d, _t: True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        created = await client.post(
            "/api/v1/workspaces",
            json={"name": "Acme Studio", "branding": {"primary_color": "#ff6600"}},
        )
        assert created.status_code == 201
        workspace = created.json()
        workspace_id = workspace["id"]
        assert workspace["role"] == "owner"
        assert workspace["slug"] == "acme-studio"

        listed = await client.get("/api/v1/workspaces")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        updated = await client.patch(
            f"/api/v1/workspaces/{workspace_id}",
            json={"name": "Acme Labs", "white_label_enabled": True},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Acme Labs"

        branded = await client.post(
            f"/api/v1/workspaces/{workspace_id}/branding",
            json={"font": "IBM Plex Sans", "support_email": "support@acme.dev"},
        )
        assert branded.status_code == 200
        assert branded.json()["branding"]["font"] == "IBM Plex Sans"
        assert branded.json()["support_email"] == "support@acme.dev"

        domain = await client.post(
            f"/api/v1/workspaces/{workspace_id}/domain",
            json={"custom_domain": "Api.Acme.dev"},
        )
        assert domain.status_code == 200
        assert domain.json()["custom_domain"] == "api.acme.dev"
        assert domain.json()["domain_verification_token"].startswith("cf-verify-")

        verify = await client.post(
            f"/api/v1/workspaces/{workspace_id}/domain/verify",
            json={"check_dns": True},
        )
        assert verify.status_code == 200
        assert verify.json()["verified"] is True


async def test_workspace_scoped_keys_posts_and_usage(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id, raw_key = _setup_auth(fake)
    _patch_supabase(monkeypatch, fake)

    class FakeTask:
        @staticmethod
        def delay(_post_id: str, _owner_id: str) -> None:
            return None

    monkeypatch.setattr("app.api.v1.posts.publish_post_task", FakeTask)

    ws_one = fake.insert_row(
        "workspaces",
        {"owner_id": user_id, "name": "One", "slug": "one"},
    )
    ws_two = fake.insert_row(
        "workspaces",
        {"owner_id": user_id, "name": "Two", "slug": "two"},
    )
    for row in fake.tables["users"]:
        if row["id"] == user_id:
            row["default_workspace_id"] = ws_one["id"]

    fake.insert_row(
        "social_accounts",
        {
            "owner_id": user_id,
            "workspace_id": ws_one["id"],
            "platform": "youtube",
            "handle": "@one",
        },
    )
    fake.insert_row(
        "social_accounts",
        {
            "owner_id": user_id,
            "workspace_id": ws_two["id"],
            "platform": "youtube",
            "handle": "@two",
        },
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        create_ws_two_key = await client.post(
            "/api/v1/keys",
            json={"name": "two-key", "workspace_id": ws_two["id"]},
        )
        assert create_ws_two_key.status_code == 201
        ws_two_key = create_ws_two_key.json()["raw_key"]

        create_ws_one_post = await client.post(
            "/api/v1/posts",
            json={"text": "one", "platforms": ["youtube"]},
            headers={"X-API-Key": raw_key, "X-Workspace-Id": ws_one["id"]},
        )
        assert create_ws_one_post.status_code == 201

        create_ws_two_post = await client.post(
            "/api/v1/posts",
            json={"text": "two", "platforms": ["youtube"]},
            headers={"X-API-Key": ws_two_key},
        )
        assert create_ws_two_post.status_code == 201

        ws_two_posts = await client.get(
            "/api/v1/posts",
            headers={"X-API-Key": ws_two_key},
        )
        assert ws_two_posts.status_code == 200
        assert ws_two_posts.json()["total"] == 1
        assert ws_two_posts.json()["data"][0]["text"] == "two"

        ws_two_usage = await client.get(
            "/api/v1/usage",
            headers={"X-API-Key": ws_two_key},
        )
        assert ws_two_usage.status_code == 200
        assert ws_two_usage.json()["posts_used"] == 1
        assert ws_two_usage.json()["accounts_used"] == 1

        wrong_workspace = await client.get(
            "/api/v1/posts",
            headers={"X-API-Key": ws_two_key, "X-Workspace-Id": ws_one["id"]},
        )
        assert wrong_workspace.status_code == 403
