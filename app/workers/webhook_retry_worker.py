"""Celery worker for retrying queued webhook deliveries."""

from __future__ import annotations

import asyncio

from app.core.webhook_dispatcher import (
    MAX_DELIVERY_ATTEMPTS,
    get_due_retry_deliveries,
    retry_delivery,
)
from app.workers.celery_app import celery_app


async def process_due_deliveries() -> dict[str, int]:
    deliveries = await get_due_retry_deliveries()

    delivered = 0
    failed = 0
    dead_letters = 0

    for delivery in deliveries:
        success = await retry_delivery(delivery)
        if success:
            delivered += 1
            continue

        if int(delivery.get("attempts") or 0) + 1 >= MAX_DELIVERY_ATTEMPTS:
            dead_letters += 1
        else:
            failed += 1

    return {
        "scanned": len(deliveries),
        "delivered": delivered,
        "failed": failed,
        "dead_letters": dead_letters,
    }


@celery_app.task(name="contentflow.retry_webhook_deliveries")
def retry_webhook_deliveries_task() -> dict[str, int]:
    return asyncio.run(process_due_deliveries())
