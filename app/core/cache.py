"""Redis-backed response caching helpers."""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, get_type_hints

from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis

from app.config import get_settings

CacheableValue = dict[str, Any] | list[Any] | str | int | float | bool | None
F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

_redis: Redis | None = None
_CACHE_NAMESPACE = "contentflow:cache"


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def reset_redis_client() -> None:
    global _redis
    _redis = None


def _extract_request(args: dict[str, Any]) -> Any | None:
    request = args.get("request")
    if request is not None:
        return request
    for value in args.values():
        if hasattr(value, "app") and hasattr(value, "scope"):
            return value
    return None


async def _resolve_redis(bound_args: dict[str, Any]) -> Redis:
    request = _extract_request(bound_args)
    redis = getattr(getattr(getattr(request, "app", None), "state", None), "redis", None)
    if redis is not None:
        return redis
    return await get_redis()


def _serialize_for_key(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_serialize_for_key(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _serialize_for_key(v) for k, v in sorted(value.items())}

    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return _serialize_for_key(dumped)

    if hasattr(value, "query_params") and hasattr(value, "path_params"):
        query = dict(value.query_params)
        path = dict(value.path_params)
        return {"query": _serialize_for_key(query), "path": _serialize_for_key(path)}

    if hasattr(value, "id"):
        return {
            "id": getattr(value, "id", None),
            "workspace_id": getattr(value, "workspace_id", None),
            "plan": getattr(value, "plan", None),
        }

    return repr(value)


def _scope_parts(bound_args: dict[str, Any]) -> tuple[str, str]:
    user = bound_args.get("user")
    user_id = "anon"
    workspace_id = "global"
    if user is not None:
        user_id = getattr(user, "id", None) or user.get("id", "anon")
        workspace_id = (
            getattr(user, "workspace_id", None)
            if hasattr(user, "workspace_id")
            else user.get("workspace_id")
        ) or "global"
    return str(user_id), str(workspace_id)


def _payload_hash(bound_args: dict[str, Any]) -> str:
    payload = {
        key: _serialize_for_key(value)
        for key, value in bound_args.items()
        if key not in {"self", "cls", "user", "response"}
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_key(key_prefix: str, bound_args: dict[str, Any]) -> str:
    user_id, workspace_id = _scope_parts(bound_args)
    suffix = _payload_hash(bound_args)
    return (
        f"{_CACHE_NAMESPACE}:{key_prefix}:user:{user_id}:"
        f"workspace:{workspace_id}:{suffix}"
    )


def _resolved_signature(func: Callable[..., Any]) -> inspect.Signature:
    signature = inspect.signature(func)
    hints = get_type_hints(func, globalns=func.__globals__, include_extras=True)
    parameters = [
        parameter.replace(annotation=hints.get(name, parameter.annotation))
        for name, parameter in signature.parameters.items()
    ]
    return signature.replace(
        parameters=parameters,
        return_annotation=hints.get("return", signature.return_annotation),
    )


def cache(*, ttl: int, key_prefix: str) -> Callable[[F], F]:
    """Cache an async endpoint or service response in Redis."""

    def decorator(func: F) -> F:
        signature = _resolved_signature(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            bound_args = dict(bound.arguments)

            try:
                redis = await _resolve_redis(bound_args)
            except Exception:
                return await func(*args, **kwargs)
            key = _cache_key(key_prefix, bound_args)

            try:
                cached = await redis.get(key)
                if cached is not None:
                    await redis.expire(key, ttl)
                    return json.loads(cached)
            except Exception:
                return await func(*args, **kwargs)

            result = await func(*args, **kwargs)
            encoded = jsonable_encoder(result)
            try:
                await redis.set(key, json.dumps(encoded), ex=ttl)
            except Exception:
                return result
            return result

        wrapper.__signature__ = signature  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


async def invalidate_user_cache(
    user_id: str,
    *,
    prefixes: list[str] | None = None,
) -> int:
    """Invalidate cached responses scoped to a user."""
    try:
        redis = await get_redis()
    except Exception:
        return 0
    prefixes_to_clear = prefixes or ["*"]
    deleted = 0

    for prefix in prefixes_to_clear:
        pattern = f"{_CACHE_NAMESPACE}:{prefix}:user:{user_id}:*"
        try:
            keys = [key async for key in redis.scan_iter(match=pattern)]
        except Exception:
            return deleted
        if keys:
            try:
                deleted += await redis.delete(*keys)
            except Exception:
                return deleted

    return deleted
