from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.services.usage_alerts import render_usage_alert_email, send_usage_alerts_if_needed
from tests.fakes import FakeSupabase


def _setup_user(fake: FakeSupabase) -> tuple[str, str]:
    user_id = str(uuid4())
    email = "usage@example.com"
    fake.insert_row("users", {"id": user_id, "email": email, "plan": "build"})
    return user_id, email


async def test_usage_thresholds_trigger(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id, email = _setup_user(fake)
    sent: list[int] = []

    async def fake_usage_summary(*args, **kwargs):
        return {
            "plan": "build",
            "posts_used": 160,
            "posts_limit": 200,
            "videos_used": 1,
            "videos_limit": 20,
            "accounts_used": 1,
            "accounts_limit": 5,
        }

    async def fake_send_template(**kwargs):
        sent.append(kwargs["variables"]["threshold"])
        fake.insert_row(
            "email_logs",
            {
                "user_id": kwargs["user_id"],
                "template": kwargs["template_name"],
                "subject": kwargs["subject"],
                "status": "sent",
            },
        )
        return {"status": "sent"}

    monkeypatch.setattr("app.services.usage_alerts.get_supabase", lambda: fake)
    monkeypatch.setattr("app.services.usage_alerts.send_template", fake_send_template)
    monkeypatch.setattr("app.services.usage_alerts.get_usage_summary", fake_usage_summary)

    thresholds = await send_usage_alerts_if_needed(
        user_id=user_id,
        email=email,
        plan="build",
        now=datetime(2026, 4, 9, tzinfo=UTC),
    )

    assert thresholds == [50, 80]
    assert sent == [50, 80]


async def test_usage_alerts_are_deduplicated(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id, email = _setup_user(fake)
    fake.insert_row(
        "email_logs",
        {
            "user_id": user_id,
            "template": "usage_alert",
            "subject": "ContentFlow usage alert 50% [2026-04]",
            "status": "sent",
        },
    )

    async def fake_usage_summary(*args, **kwargs):
        return {
            "plan": "build",
            "posts_used": 100,
            "posts_limit": 200,
            "videos_used": 0,
            "videos_limit": 20,
            "accounts_used": 1,
            "accounts_limit": 5,
        }

    async def fake_send_template(**kwargs):
        return {"status": "sent", "threshold": kwargs["variables"]["threshold"]}

    monkeypatch.setattr("app.services.usage_alerts.get_supabase", lambda: fake)
    monkeypatch.setattr("app.services.usage_alerts.send_template", fake_send_template)
    monkeypatch.setattr("app.services.usage_alerts.get_usage_summary", fake_usage_summary)

    thresholds = await send_usage_alerts_if_needed(
        user_id=user_id,
        email=email,
        plan="build",
        now=datetime(2026, 4, 9, tzinfo=UTC),
    )

    assert thresholds == []


async def test_usage_alerts_respect_notification_preferences(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id, email = _setup_user(fake)
    fake.insert_row(
        "notification_preferences",
        {"user_id": user_id, "monthly_summary": False},
    )

    async def fake_usage_summary(*args, **kwargs):
        return {
            "plan": "build",
            "posts_used": 100,
            "posts_limit": 200,
            "videos_used": 0,
            "videos_limit": 20,
            "accounts_used": 1,
            "accounts_limit": 5,
        }

    async def fake_send_template(**kwargs):
        raise AssertionError("send_template should not be called")

    monkeypatch.setattr("app.services.usage_alerts.get_supabase", lambda: fake)
    monkeypatch.setattr("app.services.usage_alerts.send_template", fake_send_template)
    monkeypatch.setattr("app.services.usage_alerts.get_usage_summary", fake_usage_summary)

    thresholds = await send_usage_alerts_if_needed(
        user_id=user_id,
        email=email,
        plan="build",
        now=datetime(2026, 4, 9, tzinfo=UTC),
    )

    assert thresholds == []


async def test_usage_alerts_reset_each_month(monkeypatch) -> None:
    fake = FakeSupabase()
    user_id, email = _setup_user(fake)
    fake.insert_row(
        "email_logs",
        {
            "user_id": user_id,
            "template": "usage_alert",
            "subject": "ContentFlow usage alert 50% [2026-03]",
            "status": "sent",
        },
    )
    sent: list[int] = []

    async def fake_usage_summary(*args, **kwargs):
        return {
            "plan": "build",
            "posts_used": 100,
            "posts_limit": 200,
            "videos_used": 0,
            "videos_limit": 20,
            "accounts_used": 1,
            "accounts_limit": 5,
        }

    async def fake_send_template(**kwargs):
        sent.append(kwargs["variables"]["threshold"])
        return {"status": "sent"}

    monkeypatch.setattr("app.services.usage_alerts.get_supabase", lambda: fake)
    monkeypatch.setattr("app.services.usage_alerts.send_template", fake_send_template)
    monkeypatch.setattr("app.services.usage_alerts.get_usage_summary", fake_usage_summary)

    thresholds = await send_usage_alerts_if_needed(
        user_id=user_id,
        email=email,
        plan="build",
        now=datetime(2026, 4, 9, tzinfo=UTC),
    )

    assert thresholds == [50]
    assert sent == [50]


def test_usage_alert_email_template_renders() -> None:
    html = render_usage_alert_email(
        {
            "plan": "build",
            "posts_used": 100,
            "posts_limit": 200,
            "videos_used": 10,
            "videos_limit": 20,
            "accounts_used": 1,
            "accounts_limit": 5,
        },
        threshold=50,
        month_key="2026-04",
    )

    assert "Usage Alert: 50%" in html
    assert "2026-04" in html
    assert "100 / 200" in html
