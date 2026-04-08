"""Webhook dispatcher with Redis-backed retry queue, DLQ, and HMAC signatures."""

from __future__ import annotations

import hmac
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import get_settings
from app.core.db import get_supabase
from app.core.logging_config import get_logger
from app.core.metrics import record_webhook_delivery
from app.core.webhook_idempotency import IdempotencyStore
from app.services.notification_service import create_notification as _create_notif

RETRY_BACKOFF_SECONDS: list[int] = [60, 300, 1800, 7200, 43200]
MAX_DELIVERY_ATTEMPTS = len(RETRY_BACKOFF_SECONDS) + 1

WEBHOOK_RETRY_QUEUE_KEY = "contentflow:webhooks:retry"
WEBHOOK_DLQ_KEY = "contentflow:webhooks:dead-letter"

SIGNATURE_HEADER = "X-ContentFlow-Signature"
TIMESTAMP_HEADER = "X-ContentFlow-Timestamp"
EVENT_HEADER = "X-ContentFlow-Event"
EVENT_ID_HEADER = "X-ContentFlow-Event-Id"
SIGNATURE_PREFIX = "sha256="

_redis: Redis | None = None
logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _stable_json(data: dict[str, Any]) -> str:
    return json.dumps(data, default=str, separators=(",", ":"), sort_keys=True)


def _build_body(event: str, payload: dict[str, Any]) -> str:
    return _stable_json({"event": event, "data": payload})


def _derive_event_id(event: str, payload: dict[str, Any]) -> str:
    explicit = payload.get("event_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return sha256(f"{event}:{_stable_json(payload)}".encode()).hexdigest()


def _event_id_from_delivery(delivery: dict[str, Any]) -> str:
    idempotency_key = delivery.get("idempotency_key")
    if isinstance(idempotency_key, str) and idempotency_key.startswith("webhook:idem:"):
        return idempotency_key.split(":", 3)[-1]
    return _derive_event_id(delivery["event"], delivery["payload"])


def _derive_replay_event_id(delivery: dict[str, Any]) -> str:
    return f"{_event_id_from_delivery(delivery)}.replay.{uuid4().hex}"


def calculate_retry_backoff_seconds(attempt: int) -> int:
    index = min(max(attempt, 1) - 1, len(RETRY_BACKOFF_SECONDS) - 1)
    return RETRY_BACKOFF_SECONDS[index]


def _build_signature(secret: str, body: str, timestamp: str) -> str:
    signed_payload = f"{timestamp}.{body}".encode()
    digest = hmac.new(secret.encode(), signed_payload, sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def _create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10.0)


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def reset_redis_client() -> None:
    global _redis
    _redis = None


def _next_retry_at(attempt: int) -> str:
    delay = calculate_retry_backoff_seconds(attempt)
    return (_utc_now() + timedelta(seconds=delay)).isoformat()


def _retry_score(timestamp: str) -> float:
    return datetime.fromisoformat(timestamp).timestamp()


async def _enqueue_retry(delivery_id: str, next_retry_at: str | None) -> None:
    if next_retry_at is None:
        return
    try:
        redis = await get_redis()
        await redis.zadd(WEBHOOK_RETRY_QUEUE_KEY, {delivery_id: _retry_score(next_retry_at)})
        await redis.zrem(WEBHOOK_DLQ_KEY, delivery_id)
    except RedisError:
        # DB state remains the source of truth; a later worker pass can recover from it.
        return


async def _remove_from_retry_queue(delivery_id: str) -> None:
    try:
        redis = await get_redis()
        await redis.zrem(WEBHOOK_RETRY_QUEUE_KEY, delivery_id)
    except RedisError:
        return


async def _move_to_dead_letter_queue(delivery_id: str) -> None:
    try:
        redis = await get_redis()
        await redis.zrem(WEBHOOK_RETRY_QUEUE_KEY, delivery_id)
        await redis.zadd(WEBHOOK_DLQ_KEY, {delivery_id: _utc_now().timestamp()})
    except RedisError:
        return


async def _get_user_webhooks(owner_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    result = (
        sb.table("webhooks")
        .select("id, owner_id, target_url, signing_secret, event_types, failure_count")
        .eq("owner_id", owner_id)
        .eq("is_active", True)
        .execute()
    )
    return result.data


def _get_webhook(webhook_id: str, owner_id: str | None = None) -> dict[str, Any] | None:
    sb = get_supabase()
    query = (
        sb.table("webhooks")
        .select("id, owner_id, target_url, signing_secret, event_types, failure_count")
        .eq("id", webhook_id)
    )
    if owner_id is not None:
        query = query.eq("owner_id", owner_id)
    return query.maybe_single().execute().data


def _get_delivery(delivery_id: str, owner_id: str | None = None) -> dict[str, Any] | None:
    sb = get_supabase()
    query = sb.table("webhook_deliveries").select("*").eq("id", delivery_id)
    if owner_id is not None:
        query = query.eq("owner_id", owner_id)
    return query.maybe_single().execute().data


def _get_delivery_by_idempotency_key(idempotency_key: str) -> dict[str, Any] | None:
    return (
        get_supabase()
        .table("webhook_deliveries")
        .select("*")
        .eq("idempotency_key", idempotency_key)
        .maybe_single()
        .execute()
        .data
    )


async def _deliver_once(
    client: httpx.AsyncClient,
    target_url: str,
    signing_secret: str,
    event: str,
    event_id: str,
    body: str,
) -> tuple[bool, str | None]:
    timestamp = str(int(_utc_now().timestamp()))
    signature = _build_signature(signing_secret, body, timestamp)
    try:
        response = await client.post(
            target_url,
            content=body,
            headers={
                "Content-Type": "application/json",
                EVENT_HEADER: event,
                EVENT_ID_HEADER: event_id,
                TIMESTAMP_HEADER: timestamp,
                SIGNATURE_HEADER: signature,
            },
        )
        if 200 <= response.status_code < 300:
            return True, None
        return False, f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        return False, str(exc)


def _record_delivery(
    webhook: dict[str, Any],
    owner_id: str,
    event: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str,
    status: str,
    attempts: int,
    last_error: str | None,
    next_retry_at: str | None,
    delivered_at: str | None,
) -> dict[str, Any]:
    sb = get_supabase()
    row = {
        "webhook_id": webhook["id"],
        "owner_id": owner_id,
        "event": event,
        "idempotency_key": idempotency_key,
        "payload": payload,
        "status": status,
        "attempts": attempts,
        "max_attempts": MAX_DELIVERY_ATTEMPTS,
        "last_error": last_error,
        "next_retry_at": next_retry_at,
        "delivered_at": delivered_at,
    }
    return sb.table("webhook_deliveries").insert(row).execute().data[0]


def _update_webhook_failure_count(webhook_id: str, failure_count: int) -> None:
    get_supabase().table("webhooks").update(
        {"failure_count": failure_count, "last_failure_at": _iso_now()},
    ).eq("id", webhook_id).execute()


def _reset_webhook_failures(webhook_id: str) -> None:
    get_supabase().table("webhooks").update(
        {"failure_count": 0, "last_failure_at": None},
    ).eq("id", webhook_id).execute()


async def dispatch_event(owner_id: str, event: str, payload: dict[str, Any]) -> None:
    webhooks = await _get_user_webhooks(owner_id)
    body = _build_body(event, payload)
    event_id = _derive_event_id(event, payload)
    idem_store = IdempotencyStore(await get_redis())

    async with _create_http_client() as client:
        for webhook in webhooks:
            if event not in (webhook.get("event_types") or []):
                continue

            idempotency_key = IdempotencyStore.key_for(webhook["id"], event_id)
            cached = await idem_store.get(idempotency_key)
            if cached and cached.get("status") == "delivered":
                logger.info(
                    "webhook_delivery_deduplicated",
                    webhook_id=webhook["id"],
                    owner_id=owner_id,
                    webhook_event=event,
                    event_id=event_id,
                )
                continue

            existing = _get_delivery_by_idempotency_key(idempotency_key)
            if existing:
                if existing.get("status") == "delivered":
                    await idem_store.store(
                        idempotency_key,
                        {
                            "status": "delivered",
                            "delivery_id": existing["id"],
                            "event_id": event_id,
                            "delivered_at": existing.get("delivered_at"),
                        },
                    )
                logger.info(
                    "webhook_delivery_duplicate_skipped",
                    webhook_id=webhook["id"],
                    owner_id=owner_id,
                    webhook_event=event,
                    event_id=event_id,
                    delivery_status=existing.get("status"),
                )
                continue

            success, error = await _deliver_once(
                client,
                webhook["target_url"],
                webhook["signing_secret"],
                event,
                event_id,
                body,
            )

            if success:
                _reset_webhook_failures(webhook["id"])
                delivery = _record_delivery(
                    webhook,
                    owner_id,
                    event,
                    payload,
                    idempotency_key=idempotency_key,
                    status="delivered",
                    attempts=1,
                    last_error=None,
                    next_retry_at=None,
                    delivered_at=_iso_now(),
                )
                await idem_store.store(
                    idempotency_key,
                    {
                        "status": "delivered",
                        "delivery_id": delivery["id"],
                        "event_id": event_id,
                        "delivered_at": delivery["delivered_at"],
                    },
                )
                record_webhook_delivery("delivered")
                continue

            next_retry_at = _next_retry_at(1)
            delivery = _record_delivery(
                webhook,
                owner_id,
                event,
                payload,
                idempotency_key=idempotency_key,
                status="pending",
                attempts=1,
                last_error=error,
                next_retry_at=next_retry_at,
                delivered_at=None,
            )
            new_count = int(webhook.get("failure_count") or 0) + 1
            _update_webhook_failure_count(webhook["id"], new_count)
            if new_count == 1:
                try:
                    _create_notif(
                        user_id=owner_id,
                        type="webhook_failed",
                        title="Webhook delivery failed",
                        body=f"Delivery to {webhook['target_url']} failed: {error}",
                        link_url="/settings/webhooks",
                    )
                except Exception:
                    pass
            await _enqueue_retry(delivery["id"], next_retry_at)
            record_webhook_delivery("pending")


async def retry_delivery(delivery: dict[str, Any]) -> bool:
    sb = get_supabase()
    await _remove_from_retry_queue(delivery["id"])
    idem_store = IdempotencyStore(await get_redis())
    idempotency_key = delivery.get("idempotency_key")
    event_id = _event_id_from_delivery(delivery)

    if idempotency_key:
        cached = await idem_store.get(idempotency_key)
        if cached and cached.get("status") == "delivered":
            sb.table("webhook_deliveries").update(
                {
                    "status": "delivered",
                    "last_error": None,
                    "next_retry_at": None,
                    "delivered_at": cached.get("delivered_at") or _iso_now(),
                },
            ).eq("id", delivery["id"]).execute()
            record_webhook_delivery("delivered")
            return True

    webhook = _get_webhook(delivery["webhook_id"])
    if not webhook:
        sb.table("webhook_deliveries").update(
            {
                "status": "dead_letter",
                "last_error": "Webhook deleted",
                "next_retry_at": None,
            },
        ).eq("id", delivery["id"]).execute()
        await _move_to_dead_letter_queue(delivery["id"])
        record_webhook_delivery("dead_letter")
        return False

    body = _build_body(delivery["event"], delivery["payload"])
    async with _create_http_client() as client:
        success, error = await _deliver_once(
            client,
            webhook["target_url"],
            webhook["signing_secret"],
            delivery["event"],
            event_id,
            body,
        )

    attempt = int(delivery.get("attempts") or 0) + 1

    if success:
        delivered_at = _iso_now()
        sb.table("webhook_deliveries").update(
            {
                "status": "delivered",
                "attempts": attempt,
                "last_error": None,
                "next_retry_at": None,
                "delivered_at": delivered_at,
            },
        ).eq("id", delivery["id"]).execute()
        _reset_webhook_failures(webhook["id"])
        if idempotency_key:
            await idem_store.store(
                idempotency_key,
                {
                    "status": "delivered",
                    "delivery_id": delivery["id"],
                    "event_id": event_id,
                    "delivered_at": delivered_at,
                },
            )
        record_webhook_delivery("delivered")
        return True

    _update_webhook_failure_count(
        webhook["id"],
        int(webhook.get("failure_count") or 0) + 1,
    )

    if attempt >= MAX_DELIVERY_ATTEMPTS:
        sb.table("webhook_deliveries").update(
            {
                "status": "dead_letter",
                "attempts": attempt,
                "last_error": error,
                "next_retry_at": None,
            },
        ).eq("id", delivery["id"]).execute()
        await _move_to_dead_letter_queue(delivery["id"])
        record_webhook_delivery("dead_letter")
        return False

    next_retry_at = _next_retry_at(attempt)
    sb.table("webhook_deliveries").update(
        {
            "status": "pending",
            "attempts": attempt,
            "last_error": error,
            "next_retry_at": next_retry_at,
        },
    ).eq("id", delivery["id"]).execute()
    await _enqueue_retry(delivery["id"], next_retry_at)
    record_webhook_delivery("pending")
    return False


async def get_pending_deliveries(limit: int = 100) -> list[dict[str, Any]]:
    sb = get_supabase()
    now = _iso_now()
    query = (
        sb.table("webhook_deliveries")
        .select("*")
        .eq("status", "pending")
        .lte("next_retry_at", now)
        .order("next_retry_at")
        .range(0, limit - 1)
    )
    return query.execute().data


async def get_due_retry_deliveries(limit: int = 100) -> list[dict[str, Any]]:
    try:
        redis = await get_redis()
        delivery_ids = await redis.zrangebyscore(
            WEBHOOK_RETRY_QUEUE_KEY,
            min="-inf",
            max=_utc_now().timestamp(),
            start=0,
            num=limit,
        )
    except RedisError:
        return await get_pending_deliveries(limit=limit)

    if not delivery_ids:
        return []

    rows = (
        get_supabase()
        .table("webhook_deliveries")
        .select("*")
        .in_("id", delivery_ids)
        .execute()
        .data
    )
    row_map = {row["id"]: row for row in rows if row.get("status") == "pending"}
    return [row_map[delivery_id] for delivery_id in delivery_ids if delivery_id in row_map]


async def replay_delivery(delivery_id: str, owner_id: str) -> dict[str, Any] | None:
    delivery = _get_delivery(delivery_id, owner_id)
    if not delivery:
        return None

    webhook = _get_webhook(delivery["webhook_id"], owner_id)
    if not webhook:
        return None

    replay = _record_delivery(
        webhook,
        owner_id,
        delivery["event"],
        delivery["payload"],
        idempotency_key=IdempotencyStore.key_for(
            webhook["id"],
            _derive_replay_event_id(delivery),
        ),
        status="pending",
        attempts=0,
        last_error=None,
        next_retry_at=_iso_now(),
        delivered_at=None,
    )
    await retry_delivery(replay)
    return _get_delivery(replay["id"], owner_id)


async def redeliver_latest_for_webhook(webhook_id: str, owner_id: str) -> dict[str, Any] | None:
    webhook = _get_webhook(webhook_id, owner_id)
    if not webhook:
        return None

    result = (
        get_supabase()
        .table("webhook_deliveries")
        .select("*")
        .eq("owner_id", owner_id)
        .eq("webhook_id", webhook_id)
        .order("created_at", desc=True)
        .range(0, 0)
        .execute()
        .data
    )
    if not result:
        return None
    return await replay_delivery(result[0]["id"], owner_id)
