"""Redis-backed HTTP response caching helpers."""

from __future__ import annotations

import fnmatch
import functools
import hashlib
import inspect
import json
import sys
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, get_type_hints

from fastapi import Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

CacheableValue = dict[str, Any] | list[Any] | str | int | float | bool | None
F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

_redis: Redis | None = None
_DEFAULT_GET_REDIS: Callable[[], Awaitable[Redis]] | None = None
_CACHE_NAMESPACE = "contentflow:response-cache"
_SAFE_METHODS = {"GET"}


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


_DEFAULT_GET_REDIS = get_redis


def reset_redis_client() -> None:
    global _redis
    _redis = None


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


def _extract_request(bound_args: dict[str, Any]) -> Any | None:
    request = bound_args.get("request")
    if request is not None:
        return request
    for value in bound_args.values():
        if hasattr(value, "method") and hasattr(value, "url") and hasattr(value, "headers"):
            return value
    return None


def _extract_response(bound_args: dict[str, Any]) -> Response | None:
    response = bound_args.get("response")
    if isinstance(response, Response):
        return response
    for value in bound_args.values():
        if isinstance(value, Response):
            return value
    return None


async def _resolve_redis(bound_args: dict[str, Any]) -> Redis:
    compat_getter = _compat_redis_getter()
    if compat_getter is not None:
        return await compat_getter()

    request = _extract_request(bound_args)
    redis = getattr(getattr(getattr(request, "app", None), "state", None), "redis", None)
    if redis is not None:
        return redis
    return await get_redis()


async def _get_compat_redis() -> Redis:
    compat_getter = _compat_redis_getter()
    if compat_getter is not None:
        return await compat_getter()
    return await get_redis()


def _compat_redis_getter() -> Callable[[], Awaitable[Redis]] | None:
    cache_module = sys.modules.get("app.core.cache")
    compat_getter = getattr(cache_module, "get_redis", None)
    if (
        callable(compat_getter)
        and compat_getter is not _DEFAULT_GET_REDIS
        and compat_getter is not get_redis
    ):
        return compat_getter
    if get_redis is not _DEFAULT_GET_REDIS:
        return get_redis
    return None


def _extract_user_id(bound_args: dict[str, Any], request: Any | None) -> str:
    user = bound_args.get("user")
    if user is not None:
        if hasattr(user, "id"):
            return str(user.id)
        if isinstance(user, dict) and user.get("id"):
            return str(user["id"])
    state_user_id = getattr(getattr(request, "state", None), "user_id", None)
    if state_user_id:
        return str(state_user_id)
    return "anon"


def _query_items(request: Any | None) -> list[tuple[str, str]]:
    if request is None:
        return []
    return sorted((str(key), str(value)) for key, value in request.query_params.multi_items())


def build_cache_hash(
    *,
    method: str,
    path: str,
    query_items: list[tuple[str, str]],
    user_id: str,
    accept_language: str,
) -> str:
    payload = {
        "method": method.upper(),
        "path": path,
        "query": query_items,
        "user_id": user_id,
        "accept_language": accept_language,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_cache_key(
    *,
    method: str,
    path: str,
    query_items: list[tuple[str, str]],
    user_id: str,
    accept_language: str,
    key_prefix: str = "response",
) -> str:
    digest = build_cache_hash(
        method=method,
        path=path,
        query_items=query_items,
        user_id=user_id,
        accept_language=accept_language,
    )
    return f"{_CACHE_NAMESPACE}:entry:{key_prefix}:{digest}"


def _user_index_key(user_id: str) -> str:
    return f"{_CACHE_NAMESPACE}:user:{user_id}"


def _path_index_key(path: str) -> str:
    return f"{_CACHE_NAMESPACE}:path:{path}"


async def _store_indexes(
    redis: Redis,
    *,
    entry_key: str,
    user_id: str,
    path: str,
    ttl: int,
    payload: dict[str, Any],
) -> None:
    pipeline = redis.pipeline()
    pipeline.set(entry_key, json.dumps(payload), ex=ttl)
    pipeline.sadd(_user_index_key(user_id), entry_key)
    pipeline.expire(_user_index_key(user_id), max(ttl, 86400))
    pipeline.sadd(_path_index_key(path), entry_key)
    pipeline.expire(_path_index_key(path), max(ttl, 86400))
    await pipeline.execute()


def _status_code_for_result(result: Any, response: Response | None) -> int:
    if isinstance(result, Response):
        return result.status_code
    if response is not None:
        return response.status_code or 200
    return 200


def _response_from_hit(
    payload: dict[str, Any],
    *,
    cache_header: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=int(payload.get("status_code", 200)),
        content=payload.get("content"),
        headers={"X-Cache": cache_header},
    )


def cached_response(
    *,
    ttl: int,
    key_prefix: str = "response",
) -> Callable[[F], F]:
    """Cache a GET endpoint response in Redis and expose HIT/MISS headers."""

    def decorator(func: F) -> F:
        signature = _resolved_signature(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            bound_args = dict(bound.arguments)
            request = _extract_request(bound_args)

            if request is None or request.method.upper() not in _SAFE_METHODS:
                return await func(*args, **kwargs)

            user_id = _extract_user_id(bound_args, request)
            accept_language = request.headers.get("accept-language", "")
            entry_key = build_cache_key(
                method=request.method,
                path=request.url.path,
                query_items=_query_items(request),
                user_id=user_id,
                accept_language=accept_language,
                key_prefix=key_prefix,
            )

            redis: Redis | None = None
            try:
                redis = await _resolve_redis(bound_args)
                cached = await redis.get(entry_key)
            except Exception:
                cached = None

            if cached is not None:
                try:
                    payload = json.loads(cached)
                except json.JSONDecodeError:
                    payload = None
                if payload is not None:
                    return _response_from_hit(payload, cache_header="HIT")

            result = await func(*args, **kwargs)
            response = _extract_response(bound_args)
            status_code = _status_code_for_result(result, response)

            if isinstance(result, Response):
                result.headers.setdefault("X-Cache", "MISS")
                return result

            payload = {
                "status_code": status_code,
                "content": jsonable_encoder(result),
            }
            if redis is None or status_code >= 400:
                return _response_from_hit(payload, cache_header="MISS")

            try:
                await _store_indexes(
                    redis,
                    entry_key=entry_key,
                    user_id=user_id,
                    path=request.url.path,
                    ttl=ttl,
                    payload=payload,
                )
            except Exception:
                return _response_from_hit(payload, cache_header="MISS")

            return _response_from_hit(payload, cache_header="MISS")

        wrapper.__signature__ = signature  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


async def invalidate_user_cache(
    user_id: str,
    *,
    prefixes: list[str] | None = None,
) -> int:
    """Invalidate cached GET responses scoped to a user."""
    try:
        redis = await _get_compat_redis()
    except Exception:
        return 0

    try:
        keys = list(await redis.smembers(_user_index_key(user_id)))
    except Exception:
        return 0

    if prefixes:
        allowed = tuple(f"{_CACHE_NAMESPACE}:entry:{prefix}:" for prefix in prefixes)
        keys = [key for key in keys if key.startswith(allowed)]

    if not keys:
        return 0

    try:
        deleted = await redis.delete(*keys)
        await redis.srem(_user_index_key(user_id), *keys)
    except Exception:
        return 0
    return int(deleted or 0)


async def invalidate_path(path_pattern: str) -> int:
    """Invalidate cached responses for paths matching a glob pattern."""
    try:
        redis = await _get_compat_redis()
    except Exception:
        return 0

    deleted = 0
    prefix = f"{_CACHE_NAMESPACE}:path:"
    try:
        index_keys = [key async for key in redis.scan_iter(match=f"{prefix}*")]
    except Exception:
        return 0

    for index_key in index_keys:
        path = index_key.removeprefix(prefix)
        if not fnmatch.fnmatch(path, path_pattern):
            continue
        try:
            members = list(await redis.smembers(index_key))
            if members:
                deleted += int(await redis.delete(*members) or 0)
            await redis.delete(index_key)
        except Exception:
            continue
    return deleted


class ResponseCacheInvalidationMiddleware(BaseHTTPMiddleware):
    """Invalidate user-scoped cache after successful write operations."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method.upper() in _SAFE_METHODS or response.status_code >= 400:
            return response

        user_id = getattr(request.state, "user_id", None)
        if user_id:
            await invalidate_user_cache(str(user_id))
        await invalidate_path(request.url.path)
        return response
