from __future__ import annotations

import gc
from collections.abc import Callable
from typing import Any

import httpx

try:
    import aiohttp
except ImportError:  # pragma: no cover - optional dependency in tests only
    aiohttp = None


class AsyncResourceTracker:
    def __init__(self) -> None:
        self._httpx_clients: list[httpx.AsyncClient] = []
        self._redis_clients: list[Any] = []
        self._aiohttp_sessions: list[Any] = []

    def track_httpx_client(self, client: httpx.AsyncClient) -> httpx.AsyncClient:
        self._httpx_clients.append(client)
        return client

    def track_redis_client(self, client: Any) -> Any:
        self._redis_clients.append(client)
        return client

    def track_aiohttp_session(self, session: Any) -> Any:
        self._aiohttp_sessions.append(session)
        return session

    def collect_garbage_resources(self) -> None:
        for obj in gc.get_objects():
            obj_type = type(obj)
            module_name = getattr(obj_type, "__module__", "")
            type_name = getattr(obj_type, "__name__", "")
            if not isinstance(module_name, str) or not isinstance(type_name, str):
                continue

            if isinstance(obj, httpx.AsyncClient):
                self.track_httpx_client(obj)
            elif (
                module_name.startswith("redis.asyncio")
                and type_name == "Redis"
            ) or (
                module_name.startswith("fakeredis.aioredis")
                and type_name == "FakeRedis"
            ):
                self.track_redis_client(obj)
            elif (
                aiohttp is not None
                and module_name.startswith("aiohttp")
                and type_name == "ClientSession"
            ):
                self.track_aiohttp_session(obj)

    async def close_all(self) -> None:
        seen: set[int] = set()

        for client in reversed(self._httpx_clients):
            if id(client) in seen:
                continue
            seen.add(id(client))
            if not client.is_closed:
                await client.aclose()

        for session in reversed(self._aiohttp_sessions):
            if id(session) in seen:
                continue
            seen.add(id(session))
            if hasattr(session, "closed") and not session.closed:
                await session.close()

        for client in reversed(self._redis_clients):
            if id(client) in seen:
                continue
            seen.add(id(client))
            close = getattr(client, "aclose", None)
            if callable(close):
                await close()


def install_resource_tracking(monkeypatch, tracker: AsyncResourceTracker) -> None:
    _wrap_init(monkeypatch, httpx.AsyncClient, tracker.track_httpx_client)


def _wrap_init(monkeypatch, cls: type[Any], tracker_fn: Callable[[Any], Any]) -> None:
    original_init = cls.__init__

    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        tracker_fn(self)

    monkeypatch.setattr(cls, "__init__", wrapped_init)
