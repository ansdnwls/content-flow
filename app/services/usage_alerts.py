"""Usage threshold email alerts with monthly deduplication."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.billing import get_usage_summary
from app.core.db import get_supabase
from app.services.email_service import render_template, send_template
from app.services.notification_service import create_notification

USAGE_ALERT_THRESHOLDS = (50, 80, 100)
USAGE_ALERT_TEMPLATE = "usage_alert"
DEFAULT_USAGE_ALERT_PREFS = {
    "product_updates": True,
    "billing": True,
    "security": True,
    "monthly_summary": True,
    "webhook_alerts": True,
}


def _month_key(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return current.strftime("%Y-%m")


def _get_or_create_preferences(user_id: str) -> dict[str, Any]:
    sb = get_supabase()
    response = (
        sb.table("notification_preferences")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    prefs = rows[0] if rows else None
    if prefs:
        return prefs
    return sb.table("notification_preferences").insert(
        {"user_id": user_id, **DEFAULT_USAGE_ALERT_PREFS},
    ).execute().data[0]


def _usage_percent(summary: dict[str, Any]) -> int:
    ratios: list[float] = []
    if summary.get("posts_limit"):
        ratios.append(summary["posts_used"] / summary["posts_limit"])
    if summary.get("videos_limit"):
        ratios.append(summary["videos_used"] / summary["videos_limit"])
    if not ratios:
        return 0
    return int(max(ratios) * 100)


def _triggered_thresholds(summary: dict[str, Any]) -> list[int]:
    usage_percent = _usage_percent(summary)
    return [threshold for threshold in USAGE_ALERT_THRESHOLDS if usage_percent >= threshold]


def _alert_subject(threshold: int, month_key: str) -> str:
    return f"ContentFlow usage alert {threshold}% [{month_key}]"


def _already_sent(user_id: str, threshold: int, month_key: str) -> bool:
    rows = (
        get_supabase()
        .table("email_logs")
        .select("*")
        .eq("user_id", user_id)
        .eq("template", USAGE_ALERT_TEMPLATE)
        .eq("subject", _alert_subject(threshold, month_key))
        .eq("status", "sent")
        .execute()
        .data
    )
    return bool(rows)


def render_usage_alert_email(summary: dict[str, Any], *, threshold: int, month_key: str) -> str:
    return render_template(
        USAGE_ALERT_TEMPLATE,
        {
            "threshold": threshold,
            "month_key": month_key,
            "usage_percent": _usage_percent(summary),
            "plan": summary["plan"],
            "posts_used": summary["posts_used"],
            "posts_limit": summary["posts_limit"],
            "videos_used": summary["videos_used"],
            "videos_limit": summary["videos_limit"],
            "accounts_used": summary["accounts_used"],
            "accounts_limit": summary["accounts_limit"],
            "dashboard_url": "https://contentflow.dev/dashboard",
            "docs_url": "https://contentflow.dev/docs",
            "unsubscribe_url": "#",
            "support_email": "support@contentflow.dev",
        },
    )


async def send_usage_alerts_if_needed(
    *,
    user_id: str,
    email: str,
    plan: str,
    workspace_id: str | None = None,
    now: datetime | None = None,
    locale: str | None = None,
) -> list[int]:
    try:
        prefs = _get_or_create_preferences(user_id)
    except Exception:
        return []

    if not prefs.get("monthly_summary", True):
        return []

    try:
        month_key = _month_key(now)
        summary = await get_usage_summary(user_id, plan, workspace_id)
        thresholds = _triggered_thresholds(summary)
    except Exception:
        return []

    sent: list[int] = []

    for threshold in thresholds:
        try:
            if _already_sent(user_id, threshold, month_key):
                continue
            result = await send_template(
                user_id=user_id,
                template_name=USAGE_ALERT_TEMPLATE,
                to=email,
                subject=_alert_subject(threshold, month_key),
                variables={
                    "threshold": threshold,
                    "month_key": month_key,
                    "usage_percent": _usage_percent(summary),
                    "plan": summary["plan"],
                    "posts_used": summary["posts_used"],
                    "posts_limit": summary["posts_limit"],
                    "videos_used": summary["videos_used"],
                    "videos_limit": summary["videos_limit"],
                    "accounts_used": summary["accounts_used"],
                    "accounts_limit": summary["accounts_limit"],
                },
                locale=locale,
            )
        except Exception:
            continue
        if result.get("status") == "sent":
            sent.append(threshold)
            if threshold == 80:
                try:
                    create_notification(
                        user_id=user_id,
                        type="quota_warning",
                        title="Usage at 80%",
                        body="You've used 80% of your monthly quota.",
                        link_url="/usage",
                    )
                except Exception:
                    pass

    return sent
