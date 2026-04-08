"""Compatibility layer for response caching helpers."""

from __future__ import annotations

from app.core.response_cache import (
    build_cache_hash,
    build_cache_key,
    cached_response,
    get_redis,
    invalidate_path,
    invalidate_user_cache,
    reset_redis_client,
)

cache = cached_response

__all__ = [
    "build_cache_hash",
    "build_cache_key",
    "cache",
    "cached_response",
    "get_redis",
    "invalidate_path",
    "invalidate_user_cache",
    "reset_redis_client",
]
