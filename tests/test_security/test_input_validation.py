"""Input validation tests — oversized payloads, invalid schemes, boundary checks."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.core.auth import build_api_key_record
from app.core.url_validator import validate_external_url
from app.main import app
from tests.fakes import FakeSupabase


@pytest.fixture()
def authed_client(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeSupabase, str]:
    fake = FakeSupabase()
    for mod in (
        "app.api.deps",
        "app.api.v1.posts",
        "app.core.billing",
    ):
        monkeypatch.setattr(f"{mod}.get_supabase", lambda: fake)
    monkeypatch.setattr(
        "app.core.workspaces.resolve_workspace_id_for_user",
        lambda *a, **kw: None,
    )

    user_id = str(uuid4())
    fake.table("users").insert({
        "id": user_id,
        "email": "v@test.com",
        "plan": "build",
        "is_active": True,
        "default_workspace_id": None,
    }).execute()

    issued, record = build_api_key_record(user_id=uuid4(), name="vk")
    record["user_id"] = user_id
    fake.table("api_keys").insert(record).execute()

    return fake, issued.raw_key


@pytest.mark.anyio()
async def test_post_text_max_length_enforced(
    authed_client: tuple[FakeSupabase, str],
) -> None:
    """Text exceeding max_length should be rejected by Pydantic."""
    _fake, key = authed_client
    payload = {
        "text": "x" * 10001,  # max_length=10000
        "platforms": ["youtube"],
    }
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/posts",
            json=payload,
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 422


@pytest.mark.anyio()
async def test_post_platforms_max_length_enforced(
    authed_client: tuple[FakeSupabase, str],
) -> None:
    """Platforms list exceeding max_length should be rejected."""
    _fake, key = authed_client
    payload = {
        "text": "test",
        "platforms": [f"platform_{i}" for i in range(21)],  # max_length=20
    }
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/posts",
            json=payload,
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 422


@pytest.mark.anyio()
async def test_bulk_post_max_100_enforced(
    authed_client: tuple[FakeSupabase, str],
) -> None:
    """Bulk posts exceeding 100 should be rejected."""
    _fake, key = authed_client
    posts = [{"text": f"p{i}", "platforms": ["youtube"]} for i in range(101)]
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/posts/bulk",
            json={"posts": posts},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 422


@pytest.mark.anyio()
async def test_empty_platforms_rejected(
    authed_client: tuple[FakeSupabase, str],
) -> None:
    """An empty platforms list should be rejected (min_length=1)."""
    _fake, key = authed_client
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/posts",
            json={"text": "hi", "platforms": []},
            headers={"X-API-Key": key},
        )
    assert resp.status_code == 422


def test_url_validator_rejects_file_scheme() -> None:
    assert validate_external_url("file:///etc/passwd") is False


def test_url_validator_rejects_data_scheme() -> None:
    assert validate_external_url("data:text/html,<h1>x</h1>") is False


def test_url_validator_accepts_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.url_validator.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("93.184.215.14", 0))],
    )
    assert validate_external_url("https://hooks.example.com/wh") is True
