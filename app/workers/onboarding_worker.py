"""Onboarding worker — email sequences for new users.

Scheduled tasks:
- 1 hour after signup: getting-started guide email
- 24 hours after signup: reminder if onboarding incomplete
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.core.db import get_supabase
from app.core.logging_config import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _send_onboarding_emails() -> dict[str, int]:
    """Check for users who need onboarding emails and send them."""
    from app.services.email_service import send_template

    sb = get_supabase()
    now = datetime.now(UTC)
    stats = {"welcome_sent": 0, "reminder_sent": 0}

    # --- 1-hour welcome guide ---
    one_hour_ago = (now - timedelta(hours=1)).isoformat()
    two_hours_ago = (now - timedelta(hours=2)).isoformat()

    recent_users = (
        sb.table("users")
        .select("id, email, language, onboarding_completed")
        .gte("created_at", two_hours_ago)
        .lte("created_at", one_hour_ago)
        .execute()
        .data
    )

    for user in recent_users:
        if user.get("onboarding_completed"):
            continue

        already_sent = (
            sb.table("email_logs")
            .select("id")
            .eq("user_id", user["id"])
            .eq("template", "onboarding_welcome")
            .execute()
            .data
        )
        if already_sent:
            continue

        try:
            await send_template(
                user_id=user["id"],
                template_name="onboarding_welcome",
                to=user["email"],
                subject="Getting started with ContentFlow",
                variables={"user_email": user["email"]},
                locale=user.get("language"),
            )
            stats["welcome_sent"] += 1
        except Exception:
            logger.exception("Failed to send welcome email to %s", user["id"])

    # --- 24-hour reminder ---
    one_day_ago = (now - timedelta(hours=24)).isoformat()
    one_day_plus_hour = (now - timedelta(hours=25)).isoformat()

    day_old_users = (
        sb.table("users")
        .select("id, email, language, onboarding_completed")
        .gte("created_at", one_day_plus_hour)
        .lte("created_at", one_day_ago)
        .execute()
        .data
    )

    for user in day_old_users:
        if user.get("onboarding_completed"):
            continue

        already_sent = (
            sb.table("email_logs")
            .select("id")
            .eq("user_id", user["id"])
            .eq("template", "onboarding_reminder")
            .execute()
            .data
        )
        if already_sent:
            continue

        try:
            await send_template(
                user_id=user["id"],
                template_name="onboarding_reminder",
                to=user["email"],
                subject="Complete your ContentFlow setup",
                variables={"user_email": user["email"]},
                locale=user.get("language"),
            )
            stats["reminder_sent"] += 1
        except Exception:
            logger.exception("Failed to send reminder email to %s", user["id"])

    return stats


@celery_app.task(name="contentflow.send_onboarding_emails")
def send_onboarding_emails() -> dict[str, int]:
    """Celery task: send onboarding email sequences."""
    return asyncio.run(_send_onboarding_emails())
