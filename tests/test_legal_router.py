"""Direct route coverage for `app/api/v1/legal.py`.

Covered routes:
- GET /api/v1/legal/dpa
- POST /api/v1/legal/dpa/sign
- GET /api/v1/legal/dpa/signed
- GET /api/v1/legal/sub-processors
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
OTHER_USER = AuthenticatedUser(
    id="user-456",
    email="other@example.com",
    plan="pro",
    is_test_key=False,
)


@pytest.fixture()
def fake_sb() -> FakeSupabase:
    return FakeSupabase()


@pytest.fixture()
def audit_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(fake_sb: FakeSupabase, audit_mock: AsyncMock):
    from app.api.deps import get_current_user

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    with (
        patch("app.api.v1.legal.get_supabase", return_value=fake_sb),
        patch("app.api.v1.legal.record_audit", new=audit_mock),
    ):
        yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture()
def anonymous_client(fake_sb: FakeSupabase, audit_mock: AsyncMock):
    app.dependency_overrides.clear()

    with (
        patch("app.api.v1.legal.get_supabase", return_value=fake_sb),
        patch("app.api.v1.legal.record_audit", new=audit_mock),
    ):
        yield TestClient(app)

    app.dependency_overrides.clear()


def test_get_dpa_requires_authentication(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/v1/legal/dpa")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-API-Key header"


def test_get_dpa_returns_current_version(client: TestClient) -> None:
    response = client.get("/api/v1/legal/dpa")

    assert response.status_code == 200
    assert response.json()["version"] == "2026-04"
    assert response.json()["sub_processors_count"] >= 4


def test_sign_dpa_requires_required_fields(client: TestClient) -> None:
    response = client.post(
        "/api/v1/legal/dpa/sign",
        json={"signer_name": "Owner", "company": "ContentFlow"},
    )

    assert response.status_code == 422


def test_sign_dpa_persists_signature_and_ip(
    client: TestClient,
    fake_sb: FakeSupabase,
    audit_mock: AsyncMock,
) -> None:
    response = client.post(
        "/api/v1/legal/dpa/sign",
        json={
            "signer_name": "Owner",
            "signer_email": "legal@example.com",
            "company": "ContentFlow",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["signed"] is True
    assert body["dpa_version"] == "2026-04"
    assert body["signed_at"]

    stored = fake_sb.tables["dpa_signatures"][0]
    assert stored["user_id"] == TEST_USER.id
    assert stored["ip"] == "testclient"
    assert stored["pdf_url"].endswith("/user-123/2026-04.pdf")
    audit_mock.assert_awaited_once()


def test_sign_dpa_duplicate_signature_returns_success(
    client: TestClient,
    fake_sb: FakeSupabase,
) -> None:
    payload = {
        "signer_name": "Owner",
        "signer_email": "legal@example.com",
        "company": "ContentFlow",
    }

    first = client.post("/api/v1/legal/dpa/sign", json=payload)
    second = client.post("/api/v1/legal/dpa/sign", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(fake_sb.tables["dpa_signatures"]) == 2


def test_get_signed_dpa_returns_not_found_without_signature(client: TestClient) -> None:
    response = client.get("/api/v1/legal/dpa/signed")

    assert response.status_code == 404
    assert "dpa_signature" in response.json()["detail"]


def test_get_signed_dpa_returns_latest_signed_record(
    client: TestClient,
    fake_sb: FakeSupabase,
) -> None:
    fake_sb.insert_row(
        "dpa_signatures",
        {
            "user_id": TEST_USER.id,
            "dpa_version": "2026-03",
            "signer_name": "Owner",
            "company": "ContentFlow",
            "signed_at": "2026-03-01T00:00:00+00:00",
            "pdf_url": "https://contentflow.dev/legal/dpa/signed/user-123/2026-03.pdf",
        },
    )
    fake_sb.insert_row(
        "dpa_signatures",
        {
            "user_id": TEST_USER.id,
            "dpa_version": "2026-04",
            "signer_name": "Owner",
            "company": "ContentFlow",
            "signed_at": "2026-04-08T00:00:00+00:00",
            "pdf_url": "https://contentflow.dev/legal/dpa/signed/user-123/2026-04.pdf",
        },
    )

    response = client.get("/api/v1/legal/dpa/signed")

    assert response.status_code == 200
    assert response.json()["dpa_version"] == "2026-04"
    assert response.json()["pdf_url"].endswith("/user-123/2026-04.pdf")


def test_get_sub_processors_lists_known_vendors(client: TestClient) -> None:
    response = client.get("/api/v1/legal/sub-processors")

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["sub_processors"]}
    assert {"Stripe", "Resend", "Supabase"} <= names


def test_get_sub_processors_response_shape(client: TestClient) -> None:
    response = client.get("/api/v1/legal/sub-processors")

    assert response.status_code == 200
    first = response.json()["sub_processors"][0]
    assert {"name", "purpose", "location", "dpa_url"} <= set(first)


def test_get_signed_dpa_does_not_expose_other_users_record(
    fake_sb: FakeSupabase,
    audit_mock: AsyncMock,
) -> None:
    from app.api.deps import get_current_user

    fake_sb.insert_row(
        "dpa_signatures",
        {
            "user_id": OTHER_USER.id,
            "dpa_version": "2026-04",
            "signer_name": "Other User",
            "company": "Elsewhere Inc",
            "signed_at": "2026-04-08T00:00:00+00:00",
            "pdf_url": "https://contentflow.dev/legal/dpa/signed/user-456/2026-04.pdf",
        },
    )

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    with (
        patch("app.api.v1.legal.get_supabase", return_value=fake_sb),
        patch("app.api.v1.legal.record_audit", new=audit_mock),
        TestClient(app) as client,
    ):
        response = client.get("/api/v1/legal/dpa/signed")

    app.dependency_overrides.clear()

    assert response.status_code == 404
