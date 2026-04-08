from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import bcrypt
from fastapi import Header

from app.config import get_settings
from app.core.errors import AuthenticationError


@dataclass(slots=True)
class IssuedApiKey:
    raw_key: str
    hashed_key: str
    key_prefix: str
    preview: str


@dataclass(slots=True)
class AuthenticatedUser:
    id: str
    email: str | None = None
    plan: str = "free"
    is_test_key: bool = False


AUTH_CACHE_NAMESPACE = "contentflow:auth"


def issue_api_key(prefix: str | None = None) -> IssuedApiKey:
    settings = get_settings()
    effective_prefix = prefix or settings.api_key_prefix
    token = secrets.token_urlsafe(settings.api_key_bytes)
    raw_key = f"{effective_prefix}_{token}"
    hashed_key = bcrypt.hashpw(
        raw_key.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    return IssuedApiKey(
        raw_key=raw_key,
        hashed_key=hashed_key,
        key_prefix=effective_prefix,
        preview=f"{effective_prefix}_...{raw_key[-4:]}",
    )


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    return bcrypt.checkpw(raw_key.encode("utf-8"), hashed_key.encode("utf-8"))


def _fingerprint_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def build_api_key_cache_key(raw_key: str, *, namespace: str) -> str:
    return f"{AUTH_CACHE_NAMESPACE}:{namespace}:{_fingerprint_api_key(raw_key)}"


def build_last_used_cache_key(api_key_id: str) -> str:
    return f"{AUTH_CACHE_NAMESPACE}:last-used:{api_key_id}"


async def get_cached_api_key_id(
    redis: Any | None,
    raw_key: str,
    *,
    namespace: str,
) -> str | None:
    if redis is None:
        return None

    try:
        cached = await redis.get(build_api_key_cache_key(raw_key, namespace=namespace))
    except Exception:
        return None

    if not cached:
        return None

    try:
        payload = json.loads(cached)
    except json.JSONDecodeError:
        return None
    api_key_id = payload.get("api_key_id")
    return api_key_id if isinstance(api_key_id, str) else None


async def cache_api_key_id(
    redis: Any | None,
    raw_key: str,
    api_key_id: str,
    *,
    namespace: str,
    ttl_seconds: int,
) -> None:
    if redis is None or ttl_seconds <= 0:
        return

    payload = json.dumps({"api_key_id": api_key_id})
    try:
        await redis.set(
            build_api_key_cache_key(raw_key, namespace=namespace),
            payload,
            ex=ttl_seconds,
        )
    except Exception:
        return


async def invalidate_cached_api_key(
    redis: Any | None,
    raw_key: str,
    *,
    namespace: str,
) -> None:
    if redis is None:
        return

    try:
        await redis.delete(build_api_key_cache_key(raw_key, namespace=namespace))
    except Exception:
        return


async def should_update_last_used(
    redis: Any | None,
    api_key_id: str,
    *,
    min_interval_seconds: int,
) -> bool:
    if redis is None or min_interval_seconds <= 0:
        return True

    try:
        updated = await redis.set(
            build_last_used_cache_key(api_key_id),
            "1",
            ex=min_interval_seconds,
            nx=True,
        )
    except Exception:
        return True
    return bool(updated)


async def get_current_user(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthenticatedUser:
    if not x_api_key:
        raise AuthenticationError("Missing X-API-Key header")

    if not x_api_key.startswith("cf_"):
        raise AuthenticationError("Invalid API key format")

    return AuthenticatedUser(
        id="dev-user",
        email="dev@contentflow.local",
        plan="free",
        is_test_key=x_api_key.startswith("cf_test_"),
    )


def build_api_key_record(
    *,
    user_id: UUID,
    name: str,
    prefix: str | None = None,
) -> tuple[IssuedApiKey, dict]:
    issued = issue_api_key(prefix=prefix)
    now = datetime.now(UTC).isoformat()
    record = {
        "user_id": str(user_id),
        "name": name,
        "key_prefix": issued.key_prefix,
        "key_preview": issued.preview,
        "hashed_key": issued.hashed_key,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    return issued, record
