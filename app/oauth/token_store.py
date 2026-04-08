"""AES-256-GCM token encryption and Supabase-backed token storage."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings
from app.core.db import get_supabase
from app.core.errors import NotFoundError

_NONCE_BYTES = 12
_AES_KEY_BYTES = 32


def _get_aes_key() -> bytes:
    key_b64 = get_settings().token_encryption_key
    if not key_b64:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not configured")

    key = base64.b64decode(key_b64)
    if len(key) != _AES_KEY_BYTES:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes for AES-256")
    return key


def encrypt_token(plaintext: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM and return a base64 string (nonce‖ciphertext)."""
    key = _get_aes_key()
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt an AES-256-GCM base64 string back to plaintext."""
    key = _get_aes_key()
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode()


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str | None
    expires_at: str | None


@dataclass(frozen=True)
class SocialAccount:
    id: str
    owner_id: str
    workspace_id: str | None
    platform: str
    handle: str
    display_name: str | None
    status: str
    token_expires_at: str | None
    metadata: dict
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class StoredAccountTokens:
    account_id: str
    owner_id: str
    platform: str
    handle: str
    display_name: str | None
    status: str
    access_token: str
    refresh_token: str | None
    expires_at: str | None
    metadata: dict


def _parse_expires_at(expires_at: str | None) -> datetime | None:
    if not expires_at:
        return None
    parsed = datetime.fromisoformat(expires_at)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _compute_expires_at(expires_in: int | None) -> str | None:
    if not expires_in:
        return None
    return (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()


def _load_account_row(account_id: str, owner_id: str) -> dict:
    sb = get_supabase()
    result = (
        sb.table("social_accounts")
        .select("*")
        .eq("id", account_id)
        .eq("owner_id", owner_id)
        .maybe_single()
        .execute()
    )
    row = result.data
    if not row:
        raise NotFoundError("SocialAccount", account_id)
    return row


def save_tokens(
    *,
    owner_id: str,
    workspace_id: str | None = None,
    platform: str,
    handle: str,
    access_token: str,
    refresh_token: str | None = None,
    token_expires_at: str | None = None,
    display_name: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Upsert a social account with encrypted tokens into Supabase."""
    sb = get_supabase()
    row = {
        "owner_id": owner_id,
        "workspace_id": workspace_id,
        "platform": platform,
        "handle": handle,
        "display_name": display_name,
        "status": "active",
        "encrypted_access_token": encrypt_token(access_token),
        "encrypted_refresh_token": encrypt_token(refresh_token) if refresh_token else None,
        "token_expires_at": token_expires_at,
        "metadata": metadata or {},
    }
    result = (
        sb.table("social_accounts")
        .upsert(row, on_conflict="owner_id,workspace_id,platform,handle")
        .execute()
    )
    return result.data[0]


def get_tokens(account_id: str, owner_id: str) -> TokenPair:
    """Load and decrypt tokens for a social account."""
    row = _load_account_row(account_id, owner_id)

    return TokenPair(
        access_token=decrypt_token(row["encrypted_access_token"]),
        refresh_token=(
            decrypt_token(row["encrypted_refresh_token"])
            if row.get("encrypted_refresh_token")
            else None
        ),
        expires_at=row.get("token_expires_at"),
    )


def get_account_tokens(account_id: str, owner_id: str) -> StoredAccountTokens:
    """Load a social account with decrypted tokens and provider metadata."""
    row = _load_account_row(account_id, owner_id)
    tokens = get_tokens(account_id, owner_id)
    return StoredAccountTokens(
        account_id=row["id"],
        owner_id=row["owner_id"],
        platform=row["platform"],
        handle=row["handle"],
        display_name=row.get("display_name"),
        status=row.get("status", "active"),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_at=tokens.expires_at,
        metadata=row.get("metadata") or {},
    )


def update_tokens(
    *,
    account_id: str,
    owner_id: str,
    access_token: str,
    refresh_token: str | None = None,
    token_expires_at: str | None = None,
) -> dict:
    """Persist refreshed OAuth tokens using AES-256 encryption."""
    sb = get_supabase()
    result = (
        sb.table("social_accounts")
        .update(
            {
                "encrypted_access_token": encrypt_token(access_token),
                "encrypted_refresh_token": (
                    encrypt_token(refresh_token) if refresh_token is not None else None
                ),
                "status": "active",
                "token_expires_at": token_expires_at,
            },
        )
        .eq("id", account_id)
        .eq("owner_id", owner_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("SocialAccount", account_id)
    return result.data[0]


async def get_valid_credentials(account_id: str, owner_id: str) -> dict[str, str]:
    """Return decrypted credentials, refreshing and re-encrypting them when needed."""
    account = get_account_tokens(account_id, owner_id)
    settings = get_settings()
    expires_at = _parse_expires_at(account.expires_at)
    now = datetime.now(UTC)
    refresh_leeway_seconds = getattr(settings, "token_refresh_leeway_seconds", 300)
    if not isinstance(refresh_leeway_seconds, (int, float)):
        refresh_leeway_seconds = 300
    leeway = timedelta(seconds=refresh_leeway_seconds)

    should_refresh = expires_at is not None and expires_at <= now + leeway
    if should_refresh:
        from app.oauth.token_refresher import refresh_account_tokens

        refreshed = await refresh_account_tokens(account.account_id, account.owner_id)
        account = get_account_tokens(
            refreshed["id"],
            refreshed["owner_id"],
        )

    if account.status == "expired":
        raise RuntimeError(f"Social account '{account.account_id}' is expired")

    credentials = {"access_token": account.access_token}
    if account.refresh_token:
        credentials["refresh_token"] = account.refresh_token
    if account.handle:
        credentials["handle"] = account.handle
    if account.display_name:
        credentials["display_name"] = account.display_name
    return credentials


def list_accounts(owner_id: str, workspace_id: str | None = None) -> list[dict]:
    """Return all social accounts for *owner_id* without token fields."""
    sb = get_supabase()
    query = (
        sb.table("social_accounts")
        .select(
            "id, workspace_id, platform, handle, display_name, "
            "status, token_expires_at, metadata"
        )
        .eq("owner_id", owner_id)
    )
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    result = query.order("created_at", desc=True).execute()
    return result.data


def mark_account_status(account_id: str, owner_id: str, status: str) -> dict:
    """Update social account status and return the updated row."""
    sb = get_supabase()
    result = (
        sb.table("social_accounts")
        .update({"status": status})
        .eq("id", account_id)
        .eq("owner_id", owner_id)
        .execute()
    )
    if not result.data:
        raise NotFoundError("SocialAccount", account_id)
    return result.data[0]


def delete_account(account_id: str, owner_id: str, workspace_id: str | None = None) -> dict | None:
    """Delete a social account and return the deleted row (or None)."""
    sb = get_supabase()
    query = sb.table("social_accounts").delete().eq("id", account_id).eq("owner_id", owner_id)
    if workspace_id is not None:
        query = query.eq("workspace_id", workspace_id)
    result = query.execute()
    return result.data[0] if result.data else None
