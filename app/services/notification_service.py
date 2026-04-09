"""In-app notification service — create, list, and manage user notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.db import get_supabase
from app.core.logging_config import get_logger

NOTIFICATION_TYPES = frozenset({
    "export_ready",
    "post_published",
    "video_ready",
    "payment_failed",
    "quota_warning",
    "webhook_failed",
    "shorts_extracted",
    "onboarding_complete",
})

logger = get_logger(__name__)


def create_notification(
    user_id: str,
    type: str,
    title: str,
    body: str,
    link_url: str | None = None,
) -> dict[str, Any]:
    """Insert a new notification row and return it."""
    if type not in NOTIFICATION_TYPES:
        raise ValueError(f"Invalid notification type: {type}")

    sb = get_supabase()
    row = {
        "user_id": user_id,
        "type": type,
        "title": title,
        "body": body,
        "link_url": link_url,
    }
    return sb.table("notifications").insert(row).execute().data[0]


def mark_read(notification_id: str, user_id: str) -> dict[str, Any] | None:
    """Mark a single notification as read. Returns updated row or None."""
    sb = get_supabase()
    result = (
        sb.table("notifications")
        .update({"read_at": datetime.now(UTC).isoformat()})
        .eq("id", notification_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def mark_all_read(user_id: str) -> int:
    """Mark all unread notifications as read. Returns count of updated rows."""
    sb = get_supabase()
    result = (
        sb.table("notifications")
        .update({"read_at": datetime.now(UTC).isoformat()})
        .eq("user_id", user_id)
        .is_("read_at", "null")
        .execute()
    )
    return len(result.data) if result.data else 0


def list_notifications(
    user_id: str,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return notifications for the user, newest first."""
    sb = get_supabase()
    query = (
        sb.table("notifications")
        .select("*")
        .eq("user_id", user_id)
    )
    if unread_only:
        query = query.is_("read_at", "null")
    query = query.order("created_at", desc=True).range(0, limit - 1)
    return query.execute().data


def get_unread_count(user_id: str) -> int:
    """Return the number of unread notifications."""
    sb = get_supabase()
    rows = (
        sb.table("notifications")
        .select("id")
        .eq("user_id", user_id)
        .is_("read_at", "null")
        .execute()
        .data
    )
    return len(rows)


def delete_notification(notification_id: str, user_id: str) -> bool:
    """Delete a single notification. Returns True if a row was deleted."""
    sb = get_supabase()
    result = (
        sb.table("notifications")
        .delete()
        .eq("id", notification_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(result.data)
