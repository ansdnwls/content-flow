"""Data retention policy enforcement — automatic cleanup of expired data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.db import get_supabase

# Retention periods per data type
RETENTION_DAYS: dict[str, int] = {
    "audit_logs": 365,
    "email_logs": 90,
    "webhook_deliveries": 30,
    "analytics_snapshots": 730,
    "trending_snapshots": 30,
}

DELETION_GRACE_DAYS = 14
PAYMENT_RECORD_RETENTION_DAYS = 365 * 7
ANONYMIZED_EMAIL_DOMAIN = "deleted.contentflow.local"


def _cutoff_iso(days: int) -> str:
    """Return ISO timestamp for `days` ago."""
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def purge_expired_data() -> dict[str, int]:
    """Delete rows past their retention period. Returns counts per table."""
    sb = get_supabase()
    results: dict[str, int] = {}

    for table_name, days in RETENTION_DAYS.items():
        cutoff = _cutoff_iso(days)
        deleted = (
            sb.table(table_name)
            .delete()
            .lte("created_at", cutoff)
            .execute()
        )
        count = len(deleted.data) if deleted.data else 0
        results[table_name] = count

    return results


def _anonymized_email(user_id: str) -> str:
    return f"deleted+{user_id[:8]}@{ANONYMIZED_EMAIL_DOMAIN}"


def process_pending_deletions() -> list[dict[str, Any]]:
    """Process deletion requests past their grace period.

    Returns list of processed deletions with user_id and status.
    """
    sb = get_supabase()
    now_iso = datetime.now(UTC).isoformat()

    pending = (
        sb.table("deletion_requests")
        .select("id, user_id, scheduled_for")
        .eq("status", "pending")
        .lte("scheduled_for", now_iso)
        .execute()
    )

    processed: list[dict[str, Any]] = []

    for req in pending.data:
        user_id = req["user_id"]

        now_iso = datetime.now(UTC).isoformat()

        # Preserve aggregate history while removing user-authored content.
        sb.table("posts").update({
            "status": "deleted_gdpr",
            "text": None,
            "media_urls": [],
            "platform_options": {},
        }).eq("owner_id", user_id).execute()
        sb.table("video_jobs").delete().eq("owner_id", user_id).execute()
        sb.table("comments").delete().eq("user_id", user_id).execute()
        sb.table("bombs").delete().eq("user_id", user_id).execute()
        sb.table("schedules").delete().eq("user_id", user_id).execute()
        sb.table("analytics_snapshots").delete().eq("owner_id", user_id).execute()
        sb.table("webhook_deliveries").delete().eq("owner_id", user_id).execute()
        sb.table("webhooks").delete().eq("owner_id", user_id).execute()
        sb.table("workspace_members").delete().eq("user_id", user_id).execute()
        sb.table("workspaces").delete().eq("owner_id", user_id).execute()

        # Delete direct personal data tables.
        for table, key in [
            ("social_accounts", "owner_id"),
            ("api_keys", "user_id"),
            ("consents", "user_id"),
            ("notification_preferences", "user_id"),
            ("email_logs", "user_id"),
            ("subscription_events", "user_id"),
        ]:
            sb.table(table).delete().eq(key, user_id).execute()

        # Preserve audit/payment evidence while stripping obvious personal content.
        sb.table("audit_logs").update({
            "metadata": {"anonymized": True, "gdpr_deleted_at": now_iso},
        }).eq("user_id", user_id).execute()
        sb.table("payments").update({
            "stripe_invoice_id": None,
        }).eq("user_id", user_id).execute()

        # Mark deletion as completed
        sb.table("deletion_requests").update({
            "status": "completed",
            "completed_at": now_iso,
        }).eq("id", req["id"]).execute()

        # Keep the user row as an anonymized placeholder so historic FK-linked
        # payment and audit records remain intact for legal retention.
        sb.table("users").update({
            "email": _anonymized_email(user_id),
            "full_name": None,
            "plan": "free",
            "is_active": False,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "subscription_status": "deleted_gdpr",
            "current_period_end": None,
            "cancel_at_period_end": False,
            "email_verified": False,
            "email_verified_at": None,
            "default_workspace_id": None,
            "data_processing_restricted": True,
            "deletion_scheduled_at": None,
        }).eq("id", user_id).execute()

        processed.append({"user_id": user_id, "status": "completed"})

    return processed


def run_retention_jobs() -> dict[str, Any]:
    """Run all retention tasks as a single operational batch."""
    purged = purge_expired_data()
    deletions = process_pending_deletions()
    return {
        "purged": purged,
        "processed_deletions": deletions,
        "payment_record_retention_days": PAYMENT_RECORD_RETENTION_DAYS,
    }
