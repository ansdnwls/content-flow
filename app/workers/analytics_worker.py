"""Celery worker for daily analytics snapshot collection."""

from __future__ import annotations

import asyncio
import logging

from app.core.db import get_supabase
from app.services.analytics_service import AnalyticsService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def collect_all_analytics() -> dict:
    """Collect analytics snapshots for all users' connected accounts."""
    sb = get_supabase()
    accounts = sb.table("social_accounts").select("*").execute().data

    service = AnalyticsService()
    collected = 0
    errors = 0

    for account in accounts:
        owner_id = account.get("owner_id")
        platform = account.get("platform")
        credentials = {
            "access_token": account.get("encrypted_access_token", ""),
        }
        if platform == "instagram":
            credentials["ig_user_id"] = account.get("handle", "")

        try:
            snapshots = await service.collect_snapshot(
                owner_id=owner_id,
                platform=platform,
                credentials=credentials,
            )
            collected += len(snapshots)
        except Exception:
            logger.exception(
                "Failed to collect analytics for %s/%s",
                owner_id,
                platform,
            )
            errors += 1

    return {"collected": collected, "accounts": len(accounts), "errors": errors}


@celery_app.task(name="contentflow.collect_analytics")
def collect_analytics_task() -> dict:
    """Celery task wrapper for analytics collection."""
    return asyncio.get_event_loop().run_until_complete(
        collect_all_analytics(),
    )
