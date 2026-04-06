"""
API Key authentication module.

Key format: cf_live_<32chars> or cf_test_<32chars>
Lookup: key_prefix from the key → search api_keys table → bcrypt verify.
"""

from __future__ import annotations

import bcrypt
from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from app.core.db import get_supabase
from app.core.errors import AuthenticationError

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    plan: str
    is_test_key: bool


def _parse_key(raw_key: str) -> tuple[str, str]:
    """Return (prefix, full_key). Raises on invalid format."""
    if not raw_key:
        raise AuthenticationError("Missing API key")
    for prefix in ("cf_live_", "cf_test_"):
        if raw_key.startswith(prefix):
            return prefix, raw_key
    raise AuthenticationError("Invalid API key format — must start with cf_live_ or cf_test_")


async def _lookup_user_by_key(prefix: str, full_key: str) -> AuthenticatedUser:
    """Query api_keys table, verify bcrypt hash, return the owning user."""
    sb = get_supabase()

    # Find active keys matching this prefix
    result = (
        sb.table("api_keys")
        .select("id, user_id, key_hash")
        .eq("key_prefix", prefix)
        .eq("is_active", True)
        .execute()
    )

    for row in result.data:
        if bcrypt.checkpw(full_key.encode("utf-8"), row["key_hash"].encode("utf-8")):
            # Found matching key — fetch user
            user_result = (
                sb.table("users")
                .select("id, email, plan")
                .eq("id", row["user_id"])
                .single()
                .execute()
            )
            user = user_result.data
            return AuthenticatedUser(
                id=user["id"],
                email=user["email"],
                plan=user["plan"],
                is_test_key=prefix == "cf_test_",
            )

    raise AuthenticationError("Invalid API key")


async def get_current_user(
    api_key: str | None = Security(_api_key_header),
) -> AuthenticatedUser:
    """FastAPI dependency — authenticate via X-API-Key header."""
    if not api_key:
        raise AuthenticationError("Missing X-API-Key header")
    prefix, full_key = _parse_key(api_key)
    return await _lookup_user_by_key(prefix, full_key)
