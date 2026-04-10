"""Billing worker — handles payment failure grace periods and downgrades."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.core.db import get_supabase
from app.workers.celery_app import celery_app

GRACE_PERIOD_DAYS = 3


async def _check_past_due_subscriptions() -> int:
    """Downgrade users whose payment has been past_due beyond the grace period.

    Returns the number of users downgraded.
    """
    sb = get_supabase()
    cutoff = (datetime.now(UTC) - timedelta(days=GRACE_PERIOD_DAYS)).isoformat()

    past_due_users = (
        sb.table("subscription_events")
        .select("user_id, created_at")
        .eq("event_type", "invoice.payment_failed")
        .lte("created_at", cutoff)
        .execute()
        .data
    )

    downgraded = 0
    seen_users: set[str] = set()

    for event in past_due_users:
        user_id = event["user_id"]
        if user_id in seen_users:
            continue
        seen_users.add(user_id)

        response = (
            sb.table("users")
            .select("id, plan, subscription_status")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        user = rows[0] if rows else None
        if not user or user.get("subscription_status") != "past_due":
            continue
        if user["plan"] == "free":
            continue

        # TODO: Send email notification before downgrading
        old_plan = user["plan"]
        sb.table("users").update({
            "plan": "free",
            "subscription_status": "canceled",
            "stripe_subscription_id": None,
            "cancel_at_period_end": False,
        }).eq("id", user_id).execute()

        sb.table("subscription_events").insert({
            "user_id": user_id,
            "event_type": "subscription.grace_period_expired",
            "from_plan": old_plan,
            "to_plan": "free",
            "metadata": {"grace_period_days": GRACE_PERIOD_DAYS},
        }).execute()

        downgraded += 1

    return downgraded


@celery_app.task(name="contentflow.check_past_due_subscriptions")
def check_past_due_subscriptions_task() -> int:
    """Celery task: check and downgrade past-due users."""
    return asyncio.run(_check_past_due_subscriptions())
