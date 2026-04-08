"""Data breach notification system — GDPR Art. 33-34 compliance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.db import get_supabase

VALID_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
INCIDENT_RESPONSE_CHECKLIST = (
    "Contain affected systems and rotate compromised credentials.",
    "Assess scope, root cause, and categories of personal data involved.",
    "Prepare supervisory authority notice within 72 hours when required.",
    "Notify affected users when there is a high risk to their rights and freedoms.",
    "Document remediation actions and long-term preventive controls.",
)


def report_breach(
    *,
    severity: str,
    description: str,
    affected_users: int | list[str] | None = None,
    affected_user_count: int | None = None,
    reported_by: str | None = None,
) -> dict[str, Any]:
    """Record a data breach incident.

    Returns the created breach record.
    """
    if severity not in VALID_SEVERITIES:
        msg = f"severity must be one of: {', '.join(sorted(VALID_SEVERITIES))}"
        raise ValueError(msg)

    if isinstance(affected_users, list):
        affected_count = len(affected_users)
    elif isinstance(affected_users, int):
        affected_count = affected_users
    else:
        affected_count = affected_user_count or 0

    sb = get_supabase()
    now_iso = datetime.now(UTC).isoformat()

    record: dict[str, Any] = {
        "severity": severity,
        "affected_user_count": affected_count,
        "description": description,
        "status": "reported",
        "created_at": now_iso,
    }
    if reported_by:
        record["reported_by"] = reported_by

    result = sb.table("data_breaches").insert(record).execute()
    stored = result.data[0] if result.data else record
    return {
        **stored,
        "notification_required": severity in {"high", "critical"},
        "authority_notification_deadline_hours": 72,
        "incident_response_checklist": list(INCIDENT_RESPONSE_CHECKLIST),
    }


def notify_affected_users(breach_id: str) -> int:
    """Mark breach as user-notified and return count of affected users.

    In production, this would trigger email notifications via the email
    service. Here we update the breach record timestamp.
    """
    sb = get_supabase()
    now_iso = datetime.now(UTC).isoformat()

    sb.table("data_breaches").update({
        "notified_users_at": now_iso,
        "status": "users_notified",
    }).eq("id", breach_id).execute()

    breach = (
        sb.table("data_breaches")
        .select("affected_user_count")
        .eq("id", breach_id)
        .maybe_single()
        .execute()
    )
    return breach.data["affected_user_count"] if breach.data else 0


def notify_authority(breach_id: str) -> dict[str, Any]:
    """Mark breach as authority-notified.

    Returns a template dict for the supervisory authority notification.
    """
    sb = get_supabase()
    now_iso = datetime.now(UTC).isoformat()

    breach_data = (
        sb.table("data_breaches")
        .select("*")
        .eq("id", breach_id)
        .maybe_single()
        .execute()
    )
    if not breach_data.data:
        return {"error": "Breach not found"}

    sb.table("data_breaches").update({
        "notified_authority_at": now_iso,
        "status": "authority_notified",
    }).eq("id", breach_id).execute()

    breach = breach_data.data
    return {
        "breach_id": breach_id,
        "severity": breach["severity"],
        "affected_user_count": breach["affected_user_count"],
        "description": breach["description"],
        "reported_at": breach["created_at"],
        "authority_notified_at": now_iso,
        "deadline_hours": 72,
        "incident_response_checklist": list(INCIDENT_RESPONSE_CHECKLIST),
        "template": "supervisory_authority_notification",
    }


def resolve_breach(breach_id: str) -> bool:
    """Mark a breach as resolved."""
    sb = get_supabase()
    now_iso = datetime.now(UTC).isoformat()

    sb.table("data_breaches").update({
        "status": "resolved",
        "resolved_at": now_iso,
    }).eq("id", breach_id).execute()

    return True


def list_breaches(*, status: str | None = None) -> list[dict[str, Any]]:
    """List all breach records, optionally filtered by status."""
    sb = get_supabase()
    query = sb.table("data_breaches").select("*")
    if status:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).execute()
    return result.data
