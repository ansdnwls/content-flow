"""Celery task entrypoint for post publishing."""

from __future__ import annotations

import asyncio

from app.services.post_service import publish_post
from app.workers.celery_app import celery_app


@celery_app.task(name="contentflow.publish_post")
def publish_post_task(post_id: str, owner_id: str) -> dict:
    results = asyncio.run(publish_post(post_id, owner_id))
    return {k: {"success": v.success, "url": v.url, "error": v.error, "platform_post_id": v.platform_post_id} for k, v in results.items()}

