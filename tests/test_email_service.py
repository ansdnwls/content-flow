"""Tests for email service — Resend SDK is mocked."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from app.services.email_service import render_template, render_text, send_email
from tests.fakes import FakeSupabase


def test_render_template_substitutes_variables() -> None:
    variables = {
        "name": "Alice",
        "dashboard_url": "https://d.io",
        "docs_url": "https://docs.io",
        "unsubscribe_url": "#",
        "support_email": "s@e.co",
    }
    html = render_template("welcome", variables)
    assert "Alice" in html
    assert "https://d.io" in html


def test_render_text_returns_none_for_missing() -> None:
    result = render_text("nonexistent_template_xyz", {})
    assert result is None


async def test_send_email_success(monkeypatch) -> None:
    fake_sb = FakeSupabase()
    user_id = str(uuid4())

    monkeypatch.setattr("app.services.email_service.get_supabase", lambda: fake_sb)

    mock_resend = MagicMock()
    mock_resend.Emails.send.return_value = {"id": "email_123"}
    monkeypatch.setattr("app.services.email_service._resend", mock_resend)

    result = await send_email(
        user_id=user_id,
        to="test@example.com",
        subject="Test",
        html="<p>Hello</p>",
    )

    assert result["status"] == "sent"
    assert len(fake_sb.tables["email_logs"]) == 1
    assert fake_sb.tables["email_logs"][0]["status"] == "sent"


async def test_send_email_failure_logged(monkeypatch) -> None:
    fake_sb = FakeSupabase()
    user_id = str(uuid4())

    monkeypatch.setattr("app.services.email_service.get_supabase", lambda: fake_sb)

    mock_resend = MagicMock()
    mock_resend.Emails.send.side_effect = RuntimeError("API down")
    monkeypatch.setattr("app.services.email_service._resend", mock_resend)

    result = await send_email(
        user_id=user_id,
        to="test@example.com",
        subject="Test",
        html="<p>Hello</p>",
    )

    assert result["status"] == "failed"
    assert len(fake_sb.tables["email_logs"]) == 1
    assert fake_sb.tables["email_logs"][0]["status"] == "failed"
    assert "API down" in fake_sb.tables["email_logs"][0]["error"]
