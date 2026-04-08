"""Direct route coverage for `app/api/v1/users.py`.

Covered routes:
- GET /api/v1/users/me
- PATCH /api/v1/users/me

Notes:
- The route schema exposes `full_name` rather than `name`.
- There is no user-id path parameter; IDOR coverage verifies extra `id` input is ignored.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedUser
from app.main import app
from tests.fakes import FakeSupabase

TEST_USER = AuthenticatedUser(
    id="user-123",
    email="owner@example.com",
    plan="pro",
    is_test_key=False,
)


@pytest.fixture()
def fake_sb() -> FakeSupabase:
    return FakeSupabase()


@pytest.fixture()
def client(fake_sb: FakeSupabase):
    from app.api.deps import get_current_user

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    with patch("app.api.v1.users.get_supabase", return_value=fake_sb):
        yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture()
def anonymous_client(fake_sb: FakeSupabase):
    app.dependency_overrides.clear()

    with patch("app.api.v1.users.get_supabase", return_value=fake_sb):
        yield TestClient(app)

    app.dependency_overrides.clear()


def test_get_me_requires_authentication(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-API-Key header"


def test_get_me_returns_profile_fields(client: TestClient, fake_sb: FakeSupabase) -> None:
    fake_sb.insert_row(
        "users",
        {
            "id": TEST_USER.id,
            "email": TEST_USER.email,
            "full_name": "Owner Name",
            "plan": "enterprise",
            "language": "ja",
            "timezone": "Asia/Tokyo",
        },
    )

    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": TEST_USER.id,
        "email": TEST_USER.email,
        "full_name": "Owner Name",
        "plan": "enterprise",
        "language": "ja",
        "timezone": "Asia/Tokyo",
    }


def test_get_me_excludes_sensitive_fields(client: TestClient, fake_sb: FakeSupabase) -> None:
    fake_sb.insert_row(
        "users",
        {
            "id": TEST_USER.id,
            "email": TEST_USER.email,
            "full_name": "Owner Name",
            "plan": TEST_USER.plan,
            "language": "ko",
            "timezone": "Asia/Seoul",
            "password_hash": "secret-hash",
        },
    )

    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    body = response.json()
    assert "password_hash" not in body
    assert set(body) == {"id", "email", "full_name", "plan", "language", "timezone"}


def test_patch_me_updates_language(client: TestClient, fake_sb: FakeSupabase) -> None:
    fake_sb.insert_row(
        "users",
        {
            "id": TEST_USER.id,
            "email": TEST_USER.email,
            "full_name": "Owner Name",
            "plan": TEST_USER.plan,
            "language": "en",
            "timezone": "UTC",
        },
    )

    response = client.patch("/api/v1/users/me", json={"language": "ko"})

    assert response.status_code == 200
    assert response.json()["language"] == "ko"
    assert fake_sb.tables["users"][0]["language"] == "ko"


def test_patch_me_updates_timezone(client: TestClient, fake_sb: FakeSupabase) -> None:
    fake_sb.insert_row(
        "users",
        {
            "id": TEST_USER.id,
            "email": TEST_USER.email,
            "full_name": "Owner Name",
            "plan": TEST_USER.plan,
            "language": "en",
            "timezone": "UTC",
        },
    )

    response = client.patch("/api/v1/users/me", json={"timezone": "Asia/Seoul"})

    assert response.status_code == 200
    assert response.json()["timezone"] == "Asia/Seoul"
    assert fake_sb.tables["users"][0]["timezone"] == "Asia/Seoul"


def test_patch_me_rejects_invalid_language(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={"language": "fr"})

    assert response.status_code == 422
    assert "Unsupported language" in response.json()["detail"]


def test_patch_me_rejects_invalid_timezone(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={"timezone": "Mars/Phobos"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported timezone"


def test_patch_me_empty_body_is_noop(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={})

    assert response.status_code == 200
    assert response.json() == {
        "id": TEST_USER.id,
        "email": TEST_USER.email,
        "full_name": None,
        "plan": TEST_USER.plan,
        "language": "ko",
        "timezone": "Asia/Seoul",
    }


def test_patch_me_ignores_attempted_id_override(client: TestClient, fake_sb: FakeSupabase) -> None:
    fake_sb.insert_row(
        "users",
        {
            "id": TEST_USER.id,
            "email": TEST_USER.email,
            "full_name": "Owner Name",
            "plan": TEST_USER.plan,
            "language": "en",
            "timezone": "UTC",
        },
    )

    response = client.patch(
        "/api/v1/users/me",
        json={"id": "user-999", "language": "ja"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == TEST_USER.id
    assert fake_sb.tables["users"][0]["id"] == TEST_USER.id
    assert fake_sb.tables["users"][0]["language"] == "ja"


def test_patch_me_updates_multiple_fields(client: TestClient, fake_sb: FakeSupabase) -> None:
    fake_sb.insert_row(
        "users",
        {
            "id": TEST_USER.id,
            "email": TEST_USER.email,
            "full_name": "Owner Name",
            "plan": TEST_USER.plan,
            "language": "en",
            "timezone": "UTC",
        },
    )

    response = client.patch(
        "/api/v1/users/me",
        json={"language": "ja", "timezone": "Asia/Tokyo"},
    )

    assert response.status_code == 200
    assert response.json()["language"] == "ja"
    assert response.json()["timezone"] == "Asia/Tokyo"
