"""Tests for platform-specific OAuth providers."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from app.oauth.providers.google import GoogleOAuthProvider
from app.oauth.providers.meta import MetaOAuthProvider
from app.oauth.providers.tiktok import TikTokOAuthProvider
from app.oauth.providers.x import XOAuthProvider, generate_pkce_pair


class _FakeSettings:
    """Minimal settings stub for provider tests."""

    oauth_redirect_base_url = "http://localhost:8000"
    google_client_id = "google-id"
    google_client_secret = "google-secret"
    meta_client_id = "meta-id"
    meta_client_secret = "meta-secret"
    tiktok_client_key = "tiktok-key"
    tiktok_client_secret = "tiktok-secret"
    x_client_id = "x-id"
    x_client_secret = "x-secret"


@pytest.fixture(autouse=True)
def _patch_settings():
    with patch("app.oauth.provider.get_settings", return_value=_FakeSettings()):
        with patch("app.oauth.providers.google.get_settings", return_value=_FakeSettings()):
            with patch("app.oauth.providers.meta.get_settings", return_value=_FakeSettings()):
                with patch(
                    "app.oauth.providers.tiktok.get_settings", return_value=_FakeSettings()
                ):
                    with patch(
                        "app.oauth.providers.x.get_settings", return_value=_FakeSettings()
                    ):
                        yield


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------
class TestGoogleProvider:
    def test_authorize_url(self):
        provider = GoogleOAuthProvider(platform="youtube")
        url = provider.get_authorize_url("test-state")
        assert "accounts.google.com" in url
        assert "test-state" in url
        assert "prompt=consent" in url
        assert "access_type=offline" in url

    @respx.mock
    async def test_exchange_code(self):
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "ya29.access",
                "refresh_token": "1//refresh",
                "expires_in": 3600,
                "token_type": "Bearer",
            })
        )
        provider = GoogleOAuthProvider(platform="youtube")
        result = await provider.exchange_code("auth-code", "http://localhost:8000/callback")
        assert result.access_token == "ya29.access"
        assert result.refresh_token == "1//refresh"

    @respx.mock
    async def test_get_user_info(self):
        respx.get("https://www.googleapis.com/oauth2/v2/userinfo").mock(
            return_value=httpx.Response(200, json={
                "id": "123",
                "email": "user@example.com",
                "name": "Test User",
                "picture": "https://example.com/photo.jpg",
            })
        )
        provider = GoogleOAuthProvider(platform="youtube")
        info = await provider.get_user_info("ya29.access")
        assert info.platform_user_id == "123"
        assert info.handle == "user@example.com"


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
class TestMetaProvider:
    def test_authorize_url(self):
        provider = MetaOAuthProvider(platform="instagram")
        url = provider.get_authorize_url("test-state")
        assert "facebook.com" in url
        assert "test-state" in url

    @respx.mock
    async def test_exchange_code_with_long_lived(self):
        # Short-lived exchange
        respx.get("https://graph.facebook.com/v19.0/oauth/access_token").mock(
            side_effect=[
                httpx.Response(200, json={"access_token": "short-lived"}),
                httpx.Response(200, json={
                    "access_token": "long-lived-token",
                    "expires_in": 5184000,
                    "token_type": "Bearer",
                }),
            ]
        )
        provider = MetaOAuthProvider(platform="instagram")
        result = await provider.exchange_code("auth-code", "http://localhost:8000/callback")
        assert result.access_token == "long-lived-token"
        assert result.refresh_token is None

    @respx.mock
    async def test_get_user_info(self):
        respx.get("https://graph.facebook.com/v19.0/me").mock(
            return_value=httpx.Response(200, json={
                "id": "456",
                "name": "Meta User",
                "email": "meta@example.com",
            })
        )
        provider = MetaOAuthProvider(platform="facebook")
        info = await provider.get_user_info("long-lived-token")
        assert info.platform_user_id == "456"
        assert info.handle == "Meta User"


# ---------------------------------------------------------------------------
# TikTok
# ---------------------------------------------------------------------------
class TestTikTokProvider:
    def test_authorize_url(self):
        provider = TikTokOAuthProvider()
        url = provider.get_authorize_url("test-state")
        assert "tiktok.com" in url
        assert "client_key=tiktok-key" in url

    @respx.mock
    async def test_exchange_code(self):
        respx.post("https://open.tiktokapis.com/v2/oauth/token/").mock(
            return_value=httpx.Response(200, json={
                "access_token": "tt-access",
                "refresh_token": "tt-refresh",
                "expires_in": 86400,
                "token_type": "Bearer",
            })
        )
        provider = TikTokOAuthProvider()
        result = await provider.exchange_code("auth-code", "http://localhost:8000/callback")
        assert result.access_token == "tt-access"
        assert result.refresh_token == "tt-refresh"

    @respx.mock
    async def test_get_user_info(self):
        respx.post("https://open.tiktokapis.com/v2/user/info/").mock(
            return_value=httpx.Response(200, json={
                "data": {"user": {
                    "open_id": "tt-789",
                    "display_name": "TikToker",
                    "avatar_url": "https://example.com/avatar.jpg",
                }}
            })
        )
        provider = TikTokOAuthProvider()
        info = await provider.get_user_info("tt-access")
        assert info.platform_user_id == "tt-789"
        assert info.display_name == "TikToker"


# ---------------------------------------------------------------------------
# X (Twitter)
# ---------------------------------------------------------------------------
class TestXProvider:
    def test_authorize_url(self):
        provider = XOAuthProvider()
        url = provider.get_authorize_url("test-state")
        assert "twitter.com" in url
        assert "code_challenge_method=S256" in url

    def test_pkce_pair(self):
        verifier, challenge = generate_pkce_pair()
        assert len(verifier) > 40
        assert len(challenge) > 20
        assert verifier != challenge

    def test_pkce_pair_unique(self):
        pair_a = generate_pkce_pair()
        pair_b = generate_pkce_pair()
        assert pair_a[0] != pair_b[0]

    @respx.mock
    async def test_exchange_code(self):
        respx.post("https://api.twitter.com/2/oauth2/token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "x-access",
                "refresh_token": "x-refresh",
                "expires_in": 7200,
                "token_type": "Bearer",
                "scope": "tweet.read tweet.write",
            })
        )
        provider = XOAuthProvider()
        result = await provider.exchange_code(
            "auth-code", "http://localhost:8000/callback", code_verifier="test-verifier"
        )
        assert result.access_token == "x-access"
        assert result.refresh_token == "x-refresh"

    @respx.mock
    async def test_get_user_info(self):
        respx.get("https://api.twitter.com/2/users/me").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "id": "x-999",
                    "name": "X User",
                    "username": "xuser",
                    "profile_image_url": "https://example.com/x.jpg",
                }
            })
        )
        provider = XOAuthProvider()
        info = await provider.get_user_info("x-access")
        assert info.platform_user_id == "x-999"
        assert info.handle == "@xuser"
