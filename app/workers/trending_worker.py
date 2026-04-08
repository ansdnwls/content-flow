"""Celery worker for periodic trending topic collection and caching."""

from __future__ import annotations

import asyncio

from app.services.trending_service import (
    SUPPORTED_PLATFORMS,
    SUPPORTED_REGIONS,
    fetch_trends,
)
from app.workers.celery_app import celery_app

# Pre-cache major platform/region combinations
_PRECACHE_COMBOS = [
    (plat, region)
    for plat in SUPPORTED_PLATFORMS
    for region in SUPPORTED_REGIONS
]


async def refresh_all_trends() -> dict[str, int]:
    """Fetch and cache trends for all platform/region combinations."""
    total = 0
    errors = 0

    for platform, region in _PRECACHE_COMBOS:
        try:
            items = await fetch_trends(
                platform=platform,
                region=region,
                category="general",
                limit=25,
                use_cache=False,
            )
            total += len(items)
        except Exception:
            errors += 1

    return {"cached_items": total, "errors": errors}


@celery_app.task(name="contentflow.refresh_trending_topics")
def refresh_trending_topics_task() -> dict[str, int]:
    """Celery task to refresh all trending caches."""
    return asyncio.run(refresh_all_trends())
