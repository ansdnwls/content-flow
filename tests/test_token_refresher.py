from __future__ import annotations

import base64
import os
from unittest.mock import AsyncMock, patch

from app.oauth.token_refresher import refresh_expiring_accounts
from app.oauth.token_store import decrypt_token, save_tokens
from tests.fakes import FakeSupabase

_TEST_KEY = base64.b64encode(os.urandom(32)).decode()


async def test_refresh_expiring_accounts_updates_tokens() -> None:
    fake = FakeSupabase()

    class FakeProvider:
        async def refresh_access_token(self, refresh_token: str):
            assert refresh_token == "refresh-1"
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
        patch("app.oauth.token_store.get_supabase", return_value=fake),
        patch("app.oauth.token_store.get_settings") as token_settings,
        patch("app.oauth.token_refresher.get_supabase", return_value=fake),
        patch("app.oauth.token_refresher.get_oauth_provider", return_value=FakeProvider()),
        patch("app.oauth.token_refresher.dispatch_event", new_callable=AsyncMock),
    ):
        token_settings.return_value.token_encryption_key = _TEST_KEY
        save_tokens(
            owner_id="owner-1",
            platform="youtube",
            handle="@channel",
            access_token="old-access",
            refresh_token="refresh-1",
            token_expires_at="2000-01-01T00:00:00+00:00",
        )
        summary = await refresh_expiring_accounts()
        stored = fake.tables["social_accounts"][0]

        assert summary["refreshed"] == 1
        assert stored["status"] == "active"
        assert decrypt_token(stored["encrypted_access_token"]) == "new-access"


async def test_refresh_failure_marks_account_expired_and_dispatches_webhook() -> None:
    fake = FakeSupabase()

    class FakeProvider:
        async def refresh_access_token(self, refresh_token: str):
            raise RuntimeError("boom")

    with (
        patch("app.oauth.token_store.get_supabase", return_value=fake),
        patch("app.oauth.token_store.get_settings") as token_settings,
        patch("app.oauth.token_refresher.get_supabase", return_value=fake),
        patch("app.oauth.token_refresher.get_oauth_provider", return_value=FakeProvider()),
        patch("app.oauth.token_refresher.dispatch_event", new_callable=AsyncMock) as dispatch_event,
    ):
        token_settings.return_value.token_encryption_key = _TEST_KEY
        save_tokens(
            owner_id="owner-2",
            platform="x_twitter",
            handle="@acct",
            access_token="old-access",
            refresh_token="refresh-2",
            token_expires_at="2000-01-01T00:00:00+00:00",
        )
        summary = await refresh_expiring_accounts()

    assert summary["expired"] == 1
    assert fake.tables["social_accounts"][0]["status"] == "expired"
    dispatch_event.assert_awaited_once()
    assert dispatch_event.await_args.args[1] == "account.disconnected"
