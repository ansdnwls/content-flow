"""Tests for Accounts API endpoints."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedUser
from app.main import app
from tests.fakes import FakeSupabase

_TEST_KEY = base64.b64encode(os.urandom(32)).decode()
_TEST_STATE_SECRET = "test-state-secret"

_TEST_USER = AuthenticatedUser(
    id="user-123",
    email="test@example.com",
    plan="build",
    is_test_key=False,
)


@pytest.fixture()
def fake_sb():
    return FakeSupabase()


@dataclass
class ClientWithDispatch:
    http: TestClient
    mock_dispatch: object

    def get(self, *args, **kwargs):
        return self.http.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        return self.http.post(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.http.delete(*args, **kwargs)


class DispatchRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    async def __call__(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))

    def assert_called_once(self) -> None:
        assert len(self.calls) == 1

    @property
    def call_args(self) -> tuple[tuple, dict]:
        return self.calls[-1]


class FakeOAuthProvider:
    platform = "youtube"

    def build_redirect_uri(self) -> str:
        return "http://localhost:8000/api/v1/accounts/callback/youtube"

    async def exchange_code(self, _code: str, _redirect_uri: str):
        from app.oauth.provider import OAuthTokenResponse

        return OAuthTokenResponse(
            access_token="ya29.test",
            refresh_token="1//refresh",
            expires_in=3600,
        )

    async def get_user_info(self, _access_token: str):
        from app.oauth.provider import OAuthUserInfo

        return OAuthUserInfo(
            platform_user_id="yt-123",
            handle="@testchannel",
            display_name="Test Channel",
            metadata={"channel_id": "UC123"},
        )


@pytest.fixture()
def client(fake_sb):
    from app.api.deps import get_current_user
    from app.config import get_settings

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER

    real_settings = get_settings()

    class PatchedSettings:
        """Proxy that overrides OAuth fields but delegates the rest."""

        token_encryption_key = _TEST_KEY
        oauth_state_secret = _TEST_STATE_SECRET
        oauth_redirect_base_url = "http://localhost:8000"
        google_client_id = "google-id"
        google_client_secret = "google-secret"
        meta_client_id = "meta-id"
        meta_client_secret = "meta-secret"
        tiktok_client_key = "tiktok-key"
        tiktok_client_secret = "tiktok-secret"
        x_client_id = "x-id"
        x_client_secret = "x-secret"

        def __getattr__(self, name):
            return getattr(real_settings, name)

    patched = PatchedSettings()
    recorder = DispatchRecorder()

    with (
        patch("app.core.db.get_supabase", return_value=fake_sb),
        patch("app.oauth.token_store.get_supabase", return_value=fake_sb),
        patch("app.oauth.token_store.get_settings", return_value=patched),
        patch("app.oauth.provider.get_settings", return_value=patched),
        patch("app.oauth.providers.google.get_settings", return_value=patched),
        patch("app.oauth.providers.meta.get_settings", return_value=patched),
        patch("app.oauth.providers.tiktok.get_settings", return_value=patched),
        patch("app.oauth.providers.x.get_settings", return_value=patched),
        patch("app.api.v1.accounts.dispatch_event", new=recorder),
    ):
        yield ClientWithDispatch(TestClient(app), recorder)

    app.dependency_overrides.clear()


class TestConnectEndpoint:
    def test_connect_youtube(self, client):
        resp = client.post("/api/v1/accounts/connect/youtube")
        assert resp.status_code == 200
        data = resp.json()
        assert "authorize_url" in data
        assert "accounts.google.com" in data["authorize_url"]

    def test_connect_tiktok(self, client):
        resp = client.post("/api/v1/accounts/connect/tiktok")
        assert resp.status_code == 200
        assert "tiktok.com" in resp.json()["authorize_url"]

    def test_connect_x_twitter(self, client):
        resp = client.post("/api/v1/accounts/connect/x_twitter")
        assert resp.status_code == 200
        url = resp.json()["authorize_url"]
        assert "twitter.com" in url
        assert "code_challenge" in url

    def test_connect_unsupported(self, client):
        resp = client.post("/api/v1/accounts/connect/linkedin")
        assert resp.status_code == 400
        assert "Unsupported platform" in resp.json()["detail"]


class TestCallbackEndpoint:
    @patch("app.api.v1.accounts.get_oauth_provider")
    def test_callback_stores_account(self, mock_get_provider, client, fake_sb):
        from app.oauth.provider import create_oauth_state

        # Create valid state
        with patch("app.oauth.provider.get_settings") as mock_s:
            mock_s.return_value.oauth_state_secret = _TEST_STATE_SECRET
            state = create_oauth_state("user-123", "youtube")

        mock_get_provider.return_value = FakeOAuthProvider()

        resp = client.get(
            f"/api/v1/accounts/callback/youtube?code=auth-code&state={state}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "youtube"
        assert data["handle"] == "@testchannel"
        assert data["display_name"] == "Test Channel"

        # Verify stored in DB
        assert len(fake_sb.tables["social_accounts"]) == 1
        stored = fake_sb.tables["social_accounts"][0]
        assert stored["owner_id"] == "user-123"

        # Verify webhook dispatched
        client.mock_dispatch.assert_called_once()
        call_args = client.mock_dispatch.call_args
        assert call_args[0][1] == "account.connected"

    def test_callback_invalid_state(self, client):
        resp = client.get("/api/v1/accounts/callback/youtube?code=test&state=invalid-jwt")
        assert resp.status_code == 400
        assert "Invalid OAuth state" in resp.json()["detail"]


class TestListEndpoint:
    def test_list_accounts(self, client, fake_sb):
        fake_sb.insert_row("social_accounts", {
            "owner_id": "user-123",
            "platform": "youtube",
            "handle": "@test",
            "display_name": "Test",
            "token_expires_at": None,
            "metadata": {},
        })
        resp = client.get("/api/v1/accounts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["data"][0]["platform"] == "youtube"

    def test_list_empty(self, client):
        resp = client.get("/api/v1/accounts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestDeleteEndpoint:
    def test_disconnect_account(self, client, fake_sb):
        row = fake_sb.insert_row("social_accounts", {
            "owner_id": "user-123",
            "platform": "instagram",
            "handle": "@insta",
            "display_name": "Insta Account",
            "token_expires_at": None,
            "metadata": {},
        })

        resp = client.delete(f"/api/v1/accounts/{row['id']}")
        assert resp.status_code == 200
        assert resp.json()["platform"] == "instagram"
        assert len(fake_sb.tables["social_accounts"]) == 0

        # Verify webhook
        client.mock_dispatch.assert_called_once()
        assert client.mock_dispatch.call_args[0][1] == "account.disconnected"

    def test_disconnect_not_found(self, client):
        resp = client.delete("/api/v1/accounts/nonexistent-id")
        assert resp.status_code == 404
