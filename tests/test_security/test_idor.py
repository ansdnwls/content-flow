"""IDOR tests — users must not access other users' resources."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.core.auth import build_api_key_record
from app.main import app
from tests.fakes import FakeSupabase


def _setup_two_users(
    fake: FakeSupabase,
) -> tuple[str, str, str, str]:
    """Create two users with API keys. Returns (user1_id, key1, user2_id, key2)."""
    user1_id = str(uuid4())
    user2_id = str(uuid4())

    for uid, email in [(user1_id, "u1@test.com"), (user2_id, "u2@test.com")]:
        fake.table("users").insert({
            "id": uid,
            "email": email,
            "plan": "build",
            "is_active": True,
            "default_workspace_id": None,
        }).execute()

    issued1, rec1 = build_api_key_record(user_id=uuid4(), name="k1")
    rec1["user_id"] = user1_id
    fake.table("api_keys").insert(rec1).execute()

    issued2, rec2 = build_api_key_record(user_id=uuid4(), name="k2")
    rec2["user_id"] = user2_id
    fake.table("api_keys").insert(rec2).execute()

    return user1_id, issued1.raw_key, user2_id, issued2.raw_key


@pytest.fixture()
def two_users(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeSupabase, str, str, str, str]:
    fake = FakeSupabase()
    for mod in (
        "app.api.deps",
        "app.api.v1.posts",
        "app.api.v1.videos",
        "app.api.v1.api_keys",
        "app.core.billing",
    ):
        monkeypatch.setattr(f"{mod}.get_supabase", lambda: fake)
    monkeypatch.setattr(
        "app.core.workspaces.resolve_workspace_id_for_user",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "app.core.workspaces.get_workspace_access",
        lambda *a, **kw: None,
    )

    u1, k1, u2, k2 = _setup_two_users(fake)
    return fake, u1, k1, u2, k2


@pytest.mark.anyio()
async def test_user_cannot_read_other_users_post(
    two_users: tuple[FakeSupabase, str, str, str, str],
) -> None:
    fake, u1, k1, u2, k2 = two_users

    # Create a post for user1
    post_id = str(uuid4())
    fake.table("posts").insert({
        "id": post_id,
        "owner_id": u1,
        "status": "pending",
        "text": "secret",
        "media_urls": [],
        "media_type": "text",
    }).execute()

    # User2 tries to read user1's post
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            f"/api/v1/posts/{post_id}",
            headers={"X-API-Key": k2},
        )
    assert resp.status_code == 404


@pytest.mark.anyio()
async def test_user_cannot_cancel_other_users_post(
    two_users: tuple[FakeSupabase, str, str, str, str],
) -> None:
    fake, u1, k1, u2, k2 = two_users

    post_id = str(uuid4())
    fake.table("posts").insert({
        "id": post_id,
        "owner_id": u1,
        "status": "pending",
        "text": "will cancel",
        "media_urls": [],
        "media_type": "text",
    }).execute()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.delete(
            f"/api/v1/posts/{post_id}",
            headers={"X-API-Key": k2},
        )
    assert resp.status_code == 404


@pytest.mark.anyio()
async def test_user_cannot_read_other_users_video(
    two_users: tuple[FakeSupabase, str, str, str, str],
) -> None:
    fake, u1, k1, u2, k2 = two_users

    video_id = str(uuid4())
    fake.table("video_jobs").insert({
        "id": video_id,
        "owner_id": u1,
        "topic": "secret",
        "mode": "legal",
        "language": "en",
        "format": "shorts",
        "status": "queued",
    }).execute()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            f"/api/v1/videos/{video_id}",
            headers={"X-API-Key": k2},
        )
    assert resp.status_code == 404


@pytest.mark.anyio()
async def test_user_cannot_list_other_users_posts(
    two_users: tuple[FakeSupabase, str, str, str, str],
) -> None:
    fake, u1, k1, u2, k2 = two_users

    fake.table("posts").insert({
        "id": str(uuid4()),
        "owner_id": u1,
        "status": "pending",
        "text": "user1 post",
        "media_urls": [],
        "media_type": "text",
    }).execute()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/api/v1/posts",
            headers={"X-API-Key": k2},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["data"] == []


@pytest.mark.anyio()
async def test_user_cannot_read_other_users_api_key(
    two_users: tuple[FakeSupabase, str, str, str, str],
) -> None:
    fake, u1, k1, u2, k2 = two_users

    # User2 tries to see user1's keys — should only see own
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/api/v1/keys",
            headers={"X-API-Key": k2},
        )
    assert resp.status_code == 200
    data = resp.json()
    # User2 should only see their own key(s)
    for key_item in data["data"]:
        assert key_item["key_preview"].startswith("cf_live")
