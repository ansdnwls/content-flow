"""Tests for email template rendering."""

from __future__ import annotations

import pytest

from app.services.email_service import render_template

TEMPLATES = [
    "welcome",
    "email_verify",
    "api_key_created",
    "payment_succeeded",
    "payment_failed",
    "subscription_canceled",
    "plan_upgraded",
    "account_disconnected",
    "webhook_failing",
    "monthly_summary",
]

COMMON_VARS = {
    "name": "TestUser",
    "dashboard_url": "https://example.com/dashboard",
    "docs_url": "https://example.com/docs",
    "unsubscribe_url": "https://example.com/unsub",
    "support_email": "support@example.com",
    "verify_url": "https://example.com/verify",
    "key_prefix": "cf_live",
    "created_at": "2026-04-07",
    "ip": "127.0.0.1",
    "amount": "$29",
    "plan": "Build",
    "invoice_url": "https://example.com/invoice",
    "retry_url": "https://example.com/retry",
    "grace_period_days": "3",
    "period_end": "2026-05-07",
    "old_plan": "Free",
    "new_plan": "Build",
    "platform": "YouTube",
    "reconnect_url": "https://example.com/reconnect",
    "webhook_url": "https://example.com/webhook",
    "failure_count": "5",
    "posts_count": "42",
    "videos_count": "7",
    "top_platforms": "YouTube, TikTok",
}


@pytest.mark.parametrize("template_name", TEMPLATES)
def test_template_renders(template_name: str) -> None:
    """Every template should render without errors."""
    html = render_template(template_name, COMMON_VARS)
    assert "TestUser" in html
    assert "<html" in html


def test_unknown_template_raises() -> None:
    with pytest.raises(FileNotFoundError):
        render_template("does_not_exist", {})
