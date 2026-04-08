"""Tests for post_service — credential loading and publish orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.adapters.base import PublishResult, RateLimitCheckResult
from tests.fakes import FakeSupabase

MODULE = "app.services.post_service"


@pytest.fixture()
def fake_sb():
    sb = FakeSupabase()
    owner_id = str(uuid4())
    post_id = str(uuid4())
    account_id = str(uuid4())

    sb.insert_row("posts", {
        "id": post_id,
        "owner_id": owner_id,
        "text": "hello world",
        "media_urls": [],
        "media_type": None,
        "platform_options": {},
        "status": "pending",
    })
    sb.insert_row("post_deliveries", {
        "post_id": post_id,
        "platform": "youtube",
        "social_account_id": account_id,
        "status": "pending",
    })

    return sb, post_id, owner_id, account_id


class TestPublishPost:
    async def test_publishes_with_valid_credentials(self, fake_sb):
        sb, post_id, owner_id, account_id = fake_sb

        mock_adapter = AsyncMock()
        mock_adapter.publish.return_value = PublishResult(
            success=True, platform_post_id="yt-999",
        )
        mock_adapter.rate_limit_check = AsyncMock(
            side_effect=[
                RateLimitCheckResult(True, remaining=5, limit=6, units_requested=1),
                RateLimitCheckResult(True, remaining=4, limit=6, units_requested=1),
            ],
        )

        with (
            patch(f"{MODULE}.get_supabase", return_value=sb),
            patch(f"{MODULE}.dispatch_event", new_callable=AsyncMock),
            patch(f"{MODULE}.ADAPTERS", {"youtube": mock_adapter}),
            patch(
                f"{MODULE}.get_valid_credentials",
                new_callable=AsyncMock,
                return_value={"access_token": "tok"},
            ),
        ):
            from app.services.post_service import publish_post

            results = await publish_post(post_id, owner_id)

        assert results["youtube"].success is True
        mock_adapter.publish.assert_called_once()
        call_creds = mock_adapter.publish.call_args[0][3]
        assert call_creds == {"access_token": "tok"}

    async def test_no_social_account_id_returns_error(self, fake_sb):
        sb, post_id, owner_id, _ = fake_sb

        # Remove social_account_id
        for d in sb.tables["post_deliveries"]:
            if d["post_id"] == post_id:
                d["social_account_id"] = None

        mock_adapter = AsyncMock()
        mock_adapter.rate_limit_check = AsyncMock()

        with (
            patch(f"{MODULE}.get_supabase", return_value=sb),
            patch(f"{MODULE}.dispatch_event", new_callable=AsyncMock),
            patch(f"{MODULE}.ADAPTERS", {"youtube": mock_adapter}),
        ):
            from app.services.post_service import publish_post

            results = await publish_post(post_id, owner_id)

        assert results["youtube"].success is False
        assert "No connected account" in results["youtube"].error
        mock_adapter.publish.assert_not_called()

    async def test_credential_error_fails_gracefully(self, fake_sb):
        sb, post_id, owner_id, _ = fake_sb

        mock_adapter = AsyncMock()
        mock_adapter.rate_limit_check = AsyncMock(
            side_effect=[
                RateLimitCheckResult(True, remaining=5, limit=6, units_requested=1),
                RateLimitCheckResult(True, remaining=4, limit=6, units_requested=1),
            ],
        )

        with (
            patch(f"{MODULE}.get_supabase", return_value=sb),
            patch(f"{MODULE}.dispatch_event", new_callable=AsyncMock),
            patch(f"{MODULE}.ADAPTERS", {"youtube": mock_adapter}),
            patch(
                f"{MODULE}.get_valid_credentials",
                new_callable=AsyncMock,
                side_effect=Exception("token decrypt failed"),
            ),
        ):
            from app.services.post_service import publish_post

            results = await publish_post(post_id, owner_id)

        assert results["youtube"].success is False
        assert "token decrypt failed" in results["youtube"].error

    async def test_partial_failure(self, fake_sb):
        sb, post_id, owner_id, _ = fake_sb

        # Add a second delivery
        acct2 = str(uuid4())
        sb.insert_row("post_deliveries", {
            "post_id": post_id,
            "platform": "tiktok",
            "social_account_id": acct2,
            "status": "pending",
        })

        yt_adapter = AsyncMock()
        yt_adapter.publish.return_value = PublishResult(success=True)
        yt_adapter.rate_limit_check = AsyncMock(
            side_effect=[
                RateLimitCheckResult(True, remaining=10, limit=25, units_requested=1),
                RateLimitCheckResult(True, remaining=9, limit=25, units_requested=1),
            ],
        )
        tt_adapter = AsyncMock()
        tt_adapter.publish.return_value = PublishResult(
            success=False, error="auth failed",
        )
        tt_adapter.rate_limit_check = AsyncMock(
            side_effect=[
                RateLimitCheckResult(True, remaining=5, limit=6, units_requested=1),
                RateLimitCheckResult(True, remaining=4, limit=6, units_requested=1),
            ],
        )

        with (
            patch(f"{MODULE}.get_supabase", return_value=sb),
            patch(f"{MODULE}.dispatch_event", new_callable=AsyncMock),
            patch(
                f"{MODULE}.ADAPTERS",
                {"youtube": yt_adapter, "tiktok": tt_adapter},
            ),
            patch(
                f"{MODULE}.get_valid_credentials",
                new_callable=AsyncMock,
                return_value={"access_token": "t"},
            ),
        ):
            from app.services.post_service import publish_post

            results = await publish_post(post_id, owner_id)

        assert results["youtube"].success is True
        assert results["tiktok"].success is False
        post = [p for p in sb.tables["posts"] if p["id"] == post_id][0]
        assert post["status"] == "partially_failed"

    async def test_all_success_dispatches_event(self, fake_sb):
        sb, post_id, owner_id, _ = fake_sb

        mock_adapter = AsyncMock()
        mock_adapter.publish.return_value = PublishResult(success=True)
        mock_adapter.rate_limit_check = AsyncMock(
            side_effect=[
                RateLimitCheckResult(True, remaining=5, limit=6, units_requested=1),
                RateLimitCheckResult(True, remaining=4, limit=6, units_requested=1),
            ],
        )

        with (
            patch(f"{MODULE}.get_supabase", return_value=sb),
            patch(f"{MODULE}.dispatch_event", new_callable=AsyncMock) as mock_evt,
            patch(f"{MODULE}.ADAPTERS", {"youtube": mock_adapter}),
            patch(
                f"{MODULE}.get_valid_credentials",
                new_callable=AsyncMock,
                return_value={"access_token": "t"},
            ),
        ):
            from app.services.post_service import publish_post

            await publish_post(post_id, owner_id)

        mock_evt.assert_called_once()
        assert mock_evt.call_args[0][1] == "post.published"

    async def test_no_adapter_for_platform(self, fake_sb):
        sb, post_id, owner_id, _ = fake_sb

        for d in sb.tables["post_deliveries"]:
            if d["post_id"] == post_id:
                d["platform"] = "unknown_platform"

        with (
            patch(f"{MODULE}.get_supabase", return_value=sb),
            patch(f"{MODULE}.dispatch_event", new_callable=AsyncMock),
            patch(f"{MODULE}.ADAPTERS", {}),
        ):
            from app.services.post_service import publish_post

            results = await publish_post(post_id, owner_id)

        assert results["unknown_platform"].success is False
        assert "No adapter" in results["unknown_platform"].error

    async def test_preflight_rate_limit_delays_whole_post(self, fake_sb):
        sb, post_id, owner_id, _ = fake_sb

        mock_adapter = AsyncMock()
        mock_adapter.rate_limit_check = AsyncMock(
            return_value=RateLimitCheckResult(
                allowed=False,
                remaining=0,
                limit=6,
                units_requested=1,
                next_available_at="2026-04-08T00:00:00+00:00",
                retry_after_seconds=3600,
            ),
        )

        with (
            patch(f"{MODULE}.get_supabase", return_value=sb),
            patch(f"{MODULE}.dispatch_event", new_callable=AsyncMock),
            patch(f"{MODULE}.ADAPTERS", {"youtube": mock_adapter}),
        ):
            from app.services.post_service import publish_post

            results = await publish_post(post_id, owner_id)

        assert results["youtube"].success is False
        assert "Platform rate limit active" in results["youtube"].error
        mock_adapter.publish.assert_not_called()
        post = [p for p in sb.tables["posts"] if p["id"] == post_id][0]
        assert post["status"] == "scheduled"
        assert post["scheduled_for"] == "2026-04-08T00:00:00+00:00"
