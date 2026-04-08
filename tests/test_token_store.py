"""Tests for AES-256-GCM token encryption and token store operations."""

from __future__ import annotations

import base64
import os
from unittest.mock import patch

import pytest
from cryptography.exceptions import InvalidTag

from app.oauth.token_store import (
    TokenPair,
    decrypt_token,
    encrypt_token,
    get_valid_credentials,
    save_tokens,
)
from tests.fakes import FakeSupabase

# Generate a deterministic 32-byte key for testing
_TEST_KEY = base64.b64encode(os.urandom(32)).decode()


@pytest.fixture(autouse=True)
def _patch_settings():
    with patch("app.oauth.token_store.get_settings") as mock:
        mock.return_value.token_encryption_key = _TEST_KEY
        yield mock


class TestEncryptDecrypt:
    def test_round_trip(self):
        plaintext = "ya29.a0ARrdaM_test_access_token"
        encrypted = encrypt_token(plaintext)
        assert decrypt_token(encrypted) == plaintext

    def test_different_nonce_different_ciphertext(self):
        plaintext = "same-token-value"
        a = encrypt_token(plaintext)
        b = encrypt_token(plaintext)
        assert a != b  # different nonce → different ciphertext
        assert decrypt_token(a) == plaintext
        assert decrypt_token(b) == plaintext

    def test_missing_key_raises(self):
        with patch("app.oauth.token_store.get_settings") as mock:
            mock.return_value.token_encryption_key = None
            with pytest.raises(RuntimeError, match="TOKEN_ENCRYPTION_KEY"):
                encrypt_token("test")

    def test_invalid_key_length_raises(self):
        short_key = base64.b64encode(os.urandom(16)).decode()
        with patch("app.oauth.token_store.get_settings") as mock:
            mock.return_value.token_encryption_key = short_key
            with pytest.raises(RuntimeError, match="exactly 32 bytes"):
                encrypt_token("test")

    def test_wrong_key_fails(self):
        encrypted = encrypt_token("secret-token")
        wrong_key = base64.b64encode(os.urandom(32)).decode()
        with patch("app.oauth.token_store.get_settings") as mock:
            mock.return_value.token_encryption_key = wrong_key
            with pytest.raises(InvalidTag):
                decrypt_token(encrypted)

    def test_empty_string_round_trip(self):
        encrypted = encrypt_token("")
        assert decrypt_token(encrypted) == ""

    def test_unicode_round_trip(self):
        plaintext = "토큰-값-유니코드"
        encrypted = encrypt_token(plaintext)
        assert decrypt_token(encrypted) == plaintext


class TestTokenPair:
    def test_frozen(self):
        tp = TokenPair(access_token="a", refresh_token="r", expires_at="2026-01-01")
        with pytest.raises(AttributeError):
            tp.access_token = "b"  # type: ignore[misc]


class TestCredentialRefresh:
    @pytest.mark.asyncio
    async def test_refreshes_expired_tokens_and_reencrypts(self):
        fake_sb = FakeSupabase()

        class FakeProvider:
            async def refresh_access_token(self, refresh_token: str):
                assert refresh_token == "old-refresh"
                return type(
                    "RefreshResult",
                    (),
                    {
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                        "expires_in": 3600,
                    },
                )()

        with (
            patch("app.oauth.token_store.get_supabase", return_value=fake_sb),
            patch("app.oauth.token_refresher.get_oauth_provider", return_value=FakeProvider()),
        ):
            row = save_tokens(
                owner_id="user-1",
                platform="youtube",
                handle="@channel",
                access_token="old-access",
                refresh_token="old-refresh",
                token_expires_at="2000-01-01T00:00:00+00:00",
            )
            stored_before = fake_sb.tables["social_accounts"][0]["encrypted_access_token"]
            credentials = await get_valid_credentials(row["id"], "user-1")

        assert credentials["access_token"] == "new-access"
        assert credentials["refresh_token"] == "new-refresh"
        stored_after = fake_sb.tables["social_accounts"][0]["encrypted_access_token"]
        assert stored_before != stored_after
        assert decrypt_token(stored_after) == "new-access"
