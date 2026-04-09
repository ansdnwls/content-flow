from __future__ import annotations

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio

from tests._resource_cleanup import AsyncResourceTracker, install_resource_tracking

aiohttp = pytest.importorskip("aiohttp")


@pytest.mark.asyncio
async def test_tracker_closes_httpx_async_clients() -> None:
    tracker = AsyncResourceTracker()
    client = tracker.track_httpx_client(httpx.AsyncClient())

    await tracker.close_all()

    assert client.is_closed is True


@pytest.mark.asyncio
async def test_tracker_ignores_already_closed_httpx_clients() -> None:
    tracker = AsyncResourceTracker()
    client = tracker.track_httpx_client(httpx.AsyncClient())
    await client.aclose()

    await tracker.close_all()

    assert client.is_closed is True


@pytest.mark.asyncio
async def test_tracker_closes_aiohttp_sessions() -> None:
    tracker = AsyncResourceTracker()
    session = tracker.track_aiohttp_session(aiohttp.ClientSession())

    await tracker.close_all()

    assert session.closed is True


@pytest.mark.asyncio
async def test_tracker_closes_redis_clients() -> None:
    tracker = AsyncResourceTracker()
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    tracker.collect_garbage_resources()

    await tracker.close_all()

    assert client.connection_pool._in_use_connections == set()


@pytest_asyncio.fixture
async def patched_tracker(monkeypatch) -> AsyncResourceTracker:
    tracker = AsyncResourceTracker()
    install_resource_tracking(monkeypatch, tracker)
    yield tracker
    await tracker.close_all()


@pytest.mark.asyncio
async def test_install_tracking_records_created_resources(
    patched_tracker: AsyncResourceTracker,
) -> None:
    client = httpx.AsyncClient()
    patched_tracker.collect_garbage_resources()

    assert client in patched_tracker._httpx_clients
