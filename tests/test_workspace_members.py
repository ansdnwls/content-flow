from __future__ import annotations

from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


def _patch(monkeypatch, fake: FakeSupabase) -> None:
    for target in (
        "app.api.deps.get_supabase",
        "app.api.v1.members.get_supabase",
        "app.core.workspaces.get_supabase",
    ):
        monkeypatch.setattr(target, lambda: fake, raising=False)


def _make_user(fake: FakeSupabase, email: str, plan: str = "build") -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row("users", {"id": user_id, "email": email, "plan": plan})
    issued, record = build_api_key_record(user_id=uuid4(), name=email.split("@")[0])
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


async def test_member_invite_update_remove(monkeypatch) -> None:
    fake = FakeSupabase()
    owner_id, owner_key = _make_user(fake, "owner@example.com")
    member_id, _member_key = _make_user(fake, "member@example.com")
    workspace = fake.insert_row(
        "workspaces",
        {"owner_id": owner_id, "name": "Team", "slug": "team"},
    )
    _patch(monkeypatch, fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": owner_key, "X-Workspace-Id": workspace["id"]},
    ) as client:
        invited = await client.post(
            f"/api/v1/workspaces/{workspace['id']}/members/invite",
            json={"user_id": member_id, "role": "viewer"},
        )
        assert invited.status_code == 201
        assert invited.json()["role"] == "viewer"

        listed = await client.get(f"/api/v1/workspaces/{workspace['id']}/members")
        assert listed.status_code == 200
        assert listed.json()["total"] == 2

        updated = await client.patch(
            f"/api/v1/workspaces/{workspace['id']}/members/{member_id}",
            json={"role": "editor"},
        )
        assert updated.status_code == 200
        assert updated.json()["role"] == "editor"

        removed = await client.delete(f"/api/v1/workspaces/{workspace['id']}/members/{member_id}")
        assert removed.status_code == 200
        assert removed.json()["status"] == "removed"


async def test_non_owner_cannot_manage_members(monkeypatch) -> None:
    fake = FakeSupabase()
    owner_id, _owner_key = _make_user(fake, "owner@example.com")
    editor_id, editor_key = _make_user(fake, "editor@example.com")
    invitee_id, _invitee_key = _make_user(fake, "invitee@example.com")
    workspace = fake.insert_row(
        "workspaces",
        {"owner_id": owner_id, "name": "Team", "slug": "team"},
    )
    fake.insert_row(
        "workspace_members",
        {"workspace_id": workspace["id"], "user_id": editor_id, "role": "editor"},
    )
    _patch(monkeypatch, fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": editor_key, "X-Workspace-Id": workspace["id"]},
    ) as client:
        resp = await client.post(
            f"/api/v1/workspaces/{workspace['id']}/members/invite",
            json={"user_id": invitee_id, "role": "viewer"},
        )
    assert resp.status_code == 403
