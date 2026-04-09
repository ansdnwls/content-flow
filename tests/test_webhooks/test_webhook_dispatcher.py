from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import fakeredis.aioredis
import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.core.webhook_dispatcher import (
    EVENT_HEADER,
    MAX_DELIVERY_ATTEMPTS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WEBHOOK_DLQ_KEY,
    WEBHOOK_RETRY_QUEUE_KEY,
    _build_signature,
    dispatch_event,
    retry_delivery,
)
from app.workers.celery_app import celery_app
from tests.fakes import FakeSupabase


def _setup_user_and_key(fake: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    fake.insert_row("users", {"id": user_id, "email": "hooks@example.com", "plan": "build"})
    issued, record = build_api_key_record(user_id=uuid4(), name="default")
    record["user_id"] = user_id
    fake.insert_row("api_keys", record)
    return user_id, issued.raw_key


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


@pytest_asyncio.fixture
async def mock_dispatcher_client(monkeypatch):
    clients: list[httpx.AsyncClient] = []

    def install(handler) -> None:
        def factory() -> httpx.AsyncClient:
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            clients.append(client)
            return client

        monkeypatch.setattr(
            "app.core.webhook_dispatcher._create_http_client",
            factory,
        )

    yield install

    for client in clients:
        await client.aclose()


async def test_dispatch_event_enqueues_failed_delivery_and_signs_request(
    monkeypatch,
    mock_dispatcher_client,
) -> None:
    fake = FakeSupabase()
    owner_id = str(uuid4())
    webhook = _add_webhook(fake, owner_id)
    redis = await _get_fake_redis()

    async def fake_get_redis():
        return redis

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        timestamp = request.headers[TIMESTAMP_HEADER]
        assert request.headers[EVENT_HEADER] == "post.published"
        assert request.headers[SIGNATURE_HEADER] == _build_signature(
            webhook["signing_secret"],
            body,
            timestamp,
        )
        return httpx.Response(500)

    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    mock_dispatcher_client(handler)

    await dispatch_event(owner_id, "post.published", {"post_id": "post-1"})

    delivery = fake.tables["webhook_deliveries"][0]
    assert delivery["status"] == "pending"
    assert delivery["attempts"] == 1
    assert delivery["last_error"] == "HTTP 500"
    assert await redis.zrange(WEBHOOK_RETRY_QUEUE_KEY, 0, -1) == [delivery["id"]]


async def test_retry_worker_processes_due_retry_queue(
    monkeypatch,
    mock_dispatcher_client,
) -> None:
    from app.workers.webhook_retry_worker import process_due_deliveries

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
            "payload": {"post_id": "post-2"},
            "status": "pending",
            "attempts": 1,
            "next_retry_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
    )
    await redis.zadd(
        WEBHOOK_RETRY_QUEUE_KEY,
        {delivery["id"]: datetime.now(UTC).timestamp() - 60},
    )

    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    mock_dispatcher_client(lambda _request: httpx.Response(200))

    result = await process_due_deliveries()

    assert result == {"scanned": 1, "delivered": 1, "failed": 0, "dead_letters": 0}
    assert fake.tables["webhook_deliveries"][0]["status"] == "delivered"
    assert await redis.zrange(WEBHOOK_RETRY_QUEUE_KEY, 0, -1) == []


async def test_retry_delivery_moves_to_dead_letter_queue(
    monkeypatch,
    mock_dispatcher_client,
) -> None:
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
            "payload": {"post_id": "post-3"},
            "status": "pending",
            "attempts": MAX_DELIVERY_ATTEMPTS - 1,
            "next_retry_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
    )
    await redis.zadd(
        WEBHOOK_RETRY_QUEUE_KEY,
        {delivery["id"]: datetime.now(UTC).timestamp() - 60},
    )

    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    mock_dispatcher_client(lambda _request: httpx.Response(500))

    delivered = await retry_delivery(delivery)

    assert delivered is False
    assert fake.tables["webhook_deliveries"][0]["status"] == "dead_letter"
    assert await redis.zrange(WEBHOOK_DLQ_KEY, 0, -1) == [delivery["id"]]


async def test_webhook_api_lists_deliveries_and_dead_letters(monkeypatch) -> None:
    from app.main import app

    fake = FakeSupabase()
    owner_id, raw_key = _setup_user_and_key(fake)
    webhook = _add_webhook(fake, owner_id)

    fake.insert_row(
        "webhook_deliveries",
        {
            "webhook_id": webhook["id"],
            "owner_id": owner_id,
            "event": "post.published",
            "payload": {"post_id": "post-4"},
            "status": "delivered",
            "attempts": 1,
            "delivered_at": datetime.now(UTC).isoformat(),
        },
    )
    fake.insert_row(
        "webhook_deliveries",
        {
            "webhook_id": webhook["id"],
            "owner_id": owner_id,
            "event": "post.published",
            "payload": {"post_id": "post-5"},
            "status": "dead_letter",
            "attempts": MAX_DELIVERY_ATTEMPTS,
            "last_error": "HTTP 500",
        },
    )

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.webhooks.get_supabase", lambda: fake)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        deliveries = await client.get(f"/api/v1/webhooks/{webhook['id']}/deliveries")
        dead_letters = await client.get("/api/v1/webhooks/dead-letters")

    assert deliveries.status_code == 200
    assert deliveries.json()["total"] == 2
    assert dead_letters.status_code == 200
    assert dead_letters.json()["total"] == 1
    assert dead_letters.json()["data"][0]["status"] == "dead_letter"


async def test_webhook_api_redeliver_and_replay(
    monkeypatch,
    mock_dispatcher_client,
) -> None:
    from app.main import app

    fake = FakeSupabase()
    owner_id, raw_key = _setup_user_and_key(fake)
    webhook = _add_webhook(fake, owner_id)
    delivery = fake.insert_row(
        "webhook_deliveries",
        {
            "webhook_id": webhook["id"],
            "owner_id": owner_id,
            "event": "post.published",
            "payload": {"post_id": "post-6"},
            "status": "dead_letter",
            "attempts": MAX_DELIVERY_ATTEMPTS,
            "last_error": "HTTP 500",
        },
    )
    redis = await _get_fake_redis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr("app.api.deps.get_supabase", lambda: fake)
    monkeypatch.setattr("app.api.v1.webhooks.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_supabase", lambda: fake)
    monkeypatch.setattr("app.core.webhook_dispatcher.get_redis", fake_get_redis)
    mock_dispatcher_client(lambda _request: httpx.Response(200))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        redeliver = await client.post(f"/api/v1/webhooks/{webhook['id']}/redeliver")
        replay = await client.post(f"/api/v1/webhooks/deliveries/{delivery['id']}/replay")

    assert redeliver.status_code == 200
    assert redeliver.json()["success"] is True
    assert redeliver.json()["delivery"]["status"] == "delivered"

    assert replay.status_code == 200
    assert replay.json()["success"] is True
    assert replay.json()["delivery"]["status"] == "delivered"
    assert len(fake.tables["webhook_deliveries"]) == 3


def test_webhook_retry_beat_schedule_registered() -> None:
    entry = celery_app.conf.beat_schedule["retry-webhook-deliveries-every-minute"]

    assert entry["task"] == "contentflow.retry_webhook_deliveries"
    assert entry["schedule"] == 60.0
