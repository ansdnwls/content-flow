"""Celery Beat scheduler tasks for due posts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.core.db import get_supabase
from app.workers.celery_app import celery_app
from app.workers.post_worker import publish_post_task


async def schedule_due_posts() -> list[str]:
    """Find due scheduled posts and enqueue them for publishing."""
    sb = get_supabase()
    now = datetime.now(UTC).isoformat()
    result = (
        sb.table("posts")
        .select("id, owner_id")
        .eq("status", "scheduled")
        .lte("scheduled_for", now)
        .execute()
    )

    queued_ids: list[str] = []
    for row in result.data:
        publish_post_task.delay(row["id"], row["owner_id"])
        sb.table("posts").update({"status": "pending"}).eq("id", row["id"]).execute()
        queued_ids.append(row["id"])

    return queued_ids


@celery_app.task(name="contentflow.schedule_due_posts")
def dispatch_due_posts_task() -> list[str]:
    """Celery Beat entrypoint that scans and enqueues due posts."""
    return asyncio.run(schedule_due_posts())
