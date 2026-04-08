from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import fakeredis.aioredis
import httpx
from redis.exceptions import RedisError

from app.core.webhook_dispatcher import (
    EVENT_ID_HEADER,
    MAX_DELIVERY_ATTEMPTS,
    WEBHOOK_DLQ_KEY,
    calculate_retry_backoff_seconds,
    dispatch_event,
    retry_delivery,
)
from app.core.webhook_idempotency import IdempotencyStore
from tests.fakes import FakeSupabase


def _add_webhook(fake: FakeSupabase, owner_id: str, **overrides) -> dict:
    return fake.insert_row(
        "webhooks",
        {
            "owner_id": owner_id,
            "target_url": "https://example.com/webhook",
            "signing_secret": "whsec_test",
            "event_types": ["post.published"],
            "is_active": True,
            "failure_count": 0,
            **overrides,
        },
    )


async def _get_fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_same_event_is_sent_only_once(monkeypatch) -> None:
    fake = FakeSupabase()
    owner_id = str(uuid4())
    _add_webhook(fake, owner_id)
    redis = await _get_fake_redis()
    calls: list[str] = []

    async def fake_get_redis():
        return redis

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers[EVENT_ID_HEADER])
        return httpx.Response(200)

    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    monkeypatch.setattr(
        "app.core.webhook_dispatcher._create_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    payload = {"post_id": "post-1"}
    await dispatch_event(owner_id, "post.published", payload)
    await dispatch_event(owner_id, "post.published", payload)

    assert len(calls) == 1
    assert len(fake.tables["webhook_deliveries"]) == 1
    assert fake.tables["webhook_deliveries"][0]["status"] == "delivered"


async def test_idempotency_store_saves_and_loads() -> None:
    redis = await _get_fake_redis()
    store = IdempotencyStore(redis)
    key = store.key_for("webhook-1", "event-1")

    saved = await store.store(key, {"status": "delivered", "delivery_id": "delivery-1"})
    loaded = await store.get(key)

    assert saved is True
    assert loaded == {"status": "delivered", "delivery_id": "delivery-1"}


async def test_retry_reuses_same_event_id(monkeypatch) -> None:
    fake = FakeSupabase()
    owner_id = str(uuid4())
    webhook = _add_webhook(fake, owner_id)
    redis = await _get_fake_redis()
    sent_event_ids: list[str] = []
    event_id = "event-retry-1"

    async def fake_get_redis():
        return redis

    delivery = fake.insert_row(
        "webhook_deliveries",
        {
            "webhook_id": webhook["id"],
            "owner_id": owner_id,
            "event": "post.published",
            "idempotency_key": IdempotencyStore.key_for(webhook["id"], event_id),
            "payload": {"post_id": "post-2"},
            "status": "pending",
            "attempts": 1,
            "next_retry_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        sent_event_ids.append(request.headers[EVENT_ID_HEADER])
        return httpx.Response(200)

    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    monkeypatch.setattr(
        "app.core.webhook_dispatcher._create_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    success = await retry_delivery(delivery)

    assert success is True
    assert sent_event_ids == [event_id]
    assert fake.tables["webhook_deliveries"][0]["idempotency_key"].endswith(event_id)


async def test_ttl_expiry_allows_store_key_to_expire() -> None:
    redis = await _get_fake_redis()
    store = IdempotencyStore(redis, ttl_seconds=1)
    key = store.key_for("webhook-1", "event-ttl")

    await store.store(key, {"status": "delivered"})
    assert await store.get(key) == {"status": "delivered"}

    await asyncio.sleep(1.1)

    assert await store.get(key) is None


async def test_failed_delivery_moves_to_dead_letter_queue(monkeypatch) -> None:
    fake = FakeSupabase()
    owner_id = str(uuid4())
    webhook = _add_webhook(fake, owner_id)
    redis = await _get_fake_redis()

    async def fake_get_redis():
        return redis

    delivery = fake.insert_row(
        "webhook_deliveries",
        {
            "webhook_id": webhook["id"],
            "owner_id": owner_id,
            "event": "post.published",
            "idempotency_key": IdempotencyStore.key_for(webhook["id"], "event-dlq"),
            "payload": {"post_id": "post-3"},
            "status": "pending",
            "attempts": MAX_DELIVERY_ATTEMPTS - 1,
            "next_retry_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
    )

    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    monkeypatch.setattr(
        "app.core.webhook_dispatcher._create_http_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
        ),
    )

    success = await retry_delivery(delivery)

    assert success is False
    assert fake.tables["webhook_deliveries"][0]["status"] == "dead_letter"
    assert await redis.zrange(WEBHOOK_DLQ_KEY, 0, -1) == [delivery["id"]]


def test_exponential_backoff_schedule() -> None:
    assert [
        calculate_retry_backoff_seconds(attempt)
        for attempt in range(1, 6)
    ] == [60, 300, 1800, 7200, 43200]


async def test_different_webhooks_are_independent(monkeypatch) -> None:
    fake = FakeSupabase()
    owner_id = str(uuid4())
    _add_webhook(fake, owner_id, target_url="https://example.com/one")
    _add_webhook(fake, owner_id, target_url="https://example.com/two")
    redis = await _get_fake_redis()
    calls: list[str] = []

    async def fake_get_redis():
        return redis

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200)

    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    monkeypatch.setattr(
        "app.core.webhook_dispatcher._create_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    await dispatch_event(owner_id, "post.published", {"post_id": "post-4"})

    assert sorted(calls) == ["https://example.com/one", "https://example.com/two"]
    assert len(fake.tables["webhook_deliveries"]) == 2


async def test_idempotency_store_handles_redis_errors() -> None:
    class BrokenRedis:
        async def get(self, _key):
            raise RedisError("boom")

        async def set(self, *_args, **_kwargs):
            raise RedisError("boom")

    store = IdempotencyStore(BrokenRedis())  # type: ignore[arg-type]

    assert await store.get("webhook:idem:test:event") is None
    assert await store.store("webhook:idem:test:event", {"status": "delivered"}) is False
