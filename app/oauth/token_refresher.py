"""Background OAuth token refresh and account expiry handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.db import get_supabase
from app.core.webhook_dispatcher import dispatch_event
from app.oauth import get_oauth_provider
from app.oauth.token_store import (
    StoredAccountTokens,
    get_account_tokens,
    mark_account_status,
    update_tokens,
)

REFRESH_SCAN_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class TokenRefreshSummary:
    scanned: int = 0
    refreshed: int = 0
    expired: int = 0
    skipped: int = 0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _compute_expires_at(expires_in: int | None) -> str | None:
    if not expires_in:
        return None
    return (_utc_now() + timedelta(seconds=expires_in)).isoformat()


def _get_refresh_source(account: StoredAccountTokens) -> str | None:
    if account.refresh_token:
        return account.refresh_token
    if account.platform in {"instagram", "facebook", "threads"}:
        return account.access_token
    return None


async def expire_account(account_id: str, owner_id: str, platform: str, reason: str) -> dict:
    row = mark_account_status(account_id, owner_id, "expired")
    await dispatch_event(
        owner_id,
        "account.disconnected",
        {
            "account_id": account_id,
            "platform": platform,
            "reason": reason,
        },
    )
    return row


async def refresh_account_tokens(account_id: str, owner_id: str) -> dict:
    account = get_account_tokens(account_id, owner_id)
    refresh_source = _get_refresh_source(account)
    if refresh_source is None:
        return await expire_account(
            account.account_id,
            account.owner_id,
            account.platform,
            "missing_refresh_token",
        )

    try:
        provider = get_oauth_provider(account.platform)
        refreshed = await provider.refresh_access_token(refresh_source)
    except Exception:
        return await expire_account(
            account.account_id,
            account.owner_id,
            account.platform,
            "token_refresh_failed",
        )

    return update_tokens(
        account_id=account.account_id,
        owner_id=account.owner_id,
        access_token=refreshed.access_token,
        refresh_token=refreshed.refresh_token or account.refresh_token,
        token_expires_at=_compute_expires_at(refreshed.expires_in),
    )


async def refresh_expiring_accounts() -> dict[str, int]:
    sb = get_supabase()
    accounts = (
        sb.table("social_accounts")
        .select("id, owner_id, platform, status, token_expires_at")
        .execute()
        .data
    )

    threshold = _utc_now() + REFRESH_SCAN_WINDOW
    summary = TokenRefreshSummary()

    for row in accounts:
        expires_at = _parse_iso(row.get("token_expires_at"))
        if row.get("status", "active") == "expired":
            summary = TokenRefreshSummary(
                scanned=summary.scanned + 1,
                refreshed=summary.refreshed,
                expired=summary.expired,
                skipped=summary.skipped + 1,
            )
            continue

        if expires_at is None or expires_at > threshold:
            summary = TokenRefreshSummary(
                scanned=summary.scanned + 1,
                refreshed=summary.refreshed,
                expired=summary.expired,
                skipped=summary.skipped + 1,
            )
            continue

        updated = await refresh_account_tokens(row["id"], row["owner_id"])
        if updated.get("status") == "expired":
            summary = TokenRefreshSummary(
                scanned=summary.scanned + 1,
                refreshed=summary.refreshed,
                expired=summary.expired + 1,
                skipped=summary.skipped,
            )
        else:
            summary = TokenRefreshSummary(
                scanned=summary.scanned + 1,
                refreshed=summary.refreshed + 1,
                expired=summary.expired,
                skipped=summary.skipped,
            )

    return {
        "scanned": summary.scanned,
        "refreshed": summary.refreshed,
        "expired": summary.expired,
        "skipped": summary.skipped,
    }
