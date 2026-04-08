"""Celery worker for periodic OAuth token refresh."""

from __future__ import annotations

import asyncio

from app.oauth.token_refresher import refresh_expiring_accounts
from app.workers.celery_app import celery_app


@celery_app.task(name="contentflow.refresh_oauth_tokens")
def refresh_oauth_tokens_task() -> dict[str, int]:
    return asyncio.run(refresh_expiring_accounts())
