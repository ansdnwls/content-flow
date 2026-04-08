"""Integration tests for Stripe billing: checkout, webhook, plan change, cancel, grace period."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.auth import build_api_key_record
from app.main import app
from app.workers.billing_worker import GRACE_PERIOD_DAYS, _check_past_due_subscriptions
from tests.fakes import FakeSupabase

BILLING_URL = "/api/v1/billing"
WEBHOOK_URL = "/api/webhooks/stripe"


def _setup(monkeypatch, *, plan: str = "free", stripe_customer_id: str | None = None):
    fake_sb = FakeSupabase()
    user_id = str(uuid4())
    user_data = {
        "id": user_id,
        "email": "billing@example.com",
        "plan": plan,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": None,
        "subscription_status": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
    }
    fake_sb.insert_row("users", user_data)

    issued, record = build_api_key_record(user_id=uuid4(), name="billing-test")
    record["user_id"] = user_id
    fake_sb.insert_row("api_keys", record)

    def fake_get_supabase():
        return fake_sb

    monkeypatch.setattr("app.api.deps.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.services.billing_service.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.api.webhooks.stripe.get_supabase", fake_get_supabase)
    monkeypatch.setattr("app.workers.billing_worker.get_supabase", fake_get_supabase)

    return fake_sb, user_id, issued.raw_key


async def test_checkout_creates_session(monkeypatch) -> None:
    """POST /billing/checkout returns a Stripe checkout URL."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_123"

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test-session"

    patch_customer = patch(
        "app.services.billing_service.stripe.Customer.create",
        return_value=mock_customer,
    )
    patch_session = patch(
        "app.services.billing_service.stripe.checkout.Session.create",
        return_value=mock_session,
    )
    with patch_customer, patch_session:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-API-Key": raw_key},
        ) as client:
            resp = await client.post(
                f"{BILLING_URL}/checkout",
                json={"plan": "build", "interval": "monthly"},
            )

    assert resp.status_code == 201
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test-session"


async def test_get_subscription_status(monkeypatch) -> None:
    """GET /billing/subscription returns plan info."""
    _fake_sb, _user_id, raw_key = _setup(monkeypatch, plan="build")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"X-API-Key": raw_key},
    ) as client:
        resp = await client.get(f"{BILLING_URL}/subscription")

    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "build"


async def test_cancel_subscription(monkeypatch) -> None:
    """POST /billing/cancel cancels at period end."""
    fake_sb, user_id, raw_key = _setup(monkeypatch, plan="scale")

    # Give user a subscription
    for row in fake_sb.tables["users"]:
        if row["id"] == user_id:
            row["stripe_subscription_id"] = "sub_test_456"

    mock_sub = MagicMock()
    mock_sub.status = "active"

    with patch("app.services.billing_service.stripe.Subscription.modify", return_value=mock_sub):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-API-Key": raw_key},
        ) as client:
            resp = await client.post(f"{BILLING_URL}/cancel")

    assert resp.status_code == 200
    body = resp.json()
    assert body["cancel_at_period_end"] is True


async def test_change_plan(monkeypatch) -> None:
    """POST /billing/change-plan switches plan with proration."""
    fake_sb, user_id, raw_key = _setup(monkeypatch, plan="build")

    for row in fake_sb.tables["users"]:
        if row["id"] == user_id:
            row["stripe_subscription_id"] = "sub_test_789"

    mock_subscription = MagicMock()
    mock_subscription.__getitem__ = lambda self, key: {
        "items": {"data": [{"id": "si_item_1"}]},
    }[key]

    mock_updated = MagicMock()
    mock_updated.status = "active"

    patch_retrieve = patch(
        "app.services.billing_service.stripe.Subscription.retrieve",
        return_value=mock_subscription,
    )
    patch_modify = patch(
        "app.services.billing_service.stripe.Subscription.modify",
        return_value=mock_updated,
    )
    with patch_retrieve, patch_modify:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-API-Key": raw_key},
        ) as client:
            resp = await client.post(
                f"{BILLING_URL}/change-plan",
                json={"plan": "scale", "interval": "monthly"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "scale"
    assert body["from_plan"] == "build"


async def test_webhook_checkout_completed(monkeypatch) -> None:
    """Stripe webhook: checkout.session.completed updates user plan."""
    fake_sb, user_id, raw_key = _setup(monkeypatch)
    customer_id = "cus_webhook_test"

    for row in fake_sb.tables["users"]:
        if row["id"] == user_id:
            row["stripe_customer_id"] = customer_id

    event_data = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": customer_id,
                "subscription": "sub_new_123",
                "metadata": {"plan": "build"},
            },
        },
    }

    mock_event = SimpleNamespace(
        type="checkout.session.completed",
        data=SimpleNamespace(
            object=event_data["data"]["object"],
        ),
    )

    with patch(
        "app.api.webhooks.stripe.stripe.Webhook.construct_event",
        return_value=mock_event,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                WEBHOOK_URL,
                content=json.dumps(event_data),
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

    assert resp.status_code == 200

    user = next(r for r in fake_sb.tables["users"] if r["id"] == user_id)
    assert user["plan"] == "build"
    assert user["subscription_status"] == "active"
    assert user["stripe_subscription_id"] == "sub_new_123"


async def test_webhook_payment_failed(monkeypatch) -> None:
    """Stripe webhook: invoice.payment_failed sets status to past_due."""
    fake_sb, user_id, _raw_key = _setup(monkeypatch, plan="build")
    customer_id = "cus_fail_test"

    for row in fake_sb.tables["users"]:
        if row["id"] == user_id:
            row["stripe_customer_id"] = customer_id

    mock_event = SimpleNamespace(
        type="invoice.payment_failed",
        data=SimpleNamespace(
            object={
                "customer": customer_id,
                "id": "inv_failed_123",
            },
        ),
    )

    with patch(
        "app.api.webhooks.stripe.stripe.Webhook.construct_event",
        return_value=mock_event,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            resp = await client.post(
                WEBHOOK_URL,
                content=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": "t=123,v1=abc",
                },
            )

    assert resp.status_code == 200
    user = next(r for r in fake_sb.tables["users"] if r["id"] == user_id)
    assert user["subscription_status"] == "past_due"


async def test_grace_period_downgrade(monkeypatch) -> None:
    """Billing worker downgrades past_due users after grace period."""
    fake_sb, user_id, _raw_key = _setup(monkeypatch, plan="scale")

    for row in fake_sb.tables["users"]:
        if row["id"] == user_id:
            row["subscription_status"] = "past_due"

    # Insert a payment_failed event older than grace period
    old_date = (datetime.now(UTC) - timedelta(days=GRACE_PERIOD_DAYS + 1)).isoformat()
    fake_sb.insert_row("subscription_events", {
        "user_id": user_id,
        "event_type": "invoice.payment_failed",
        "from_plan": "scale",
        "to_plan": "scale",
        "created_at": old_date,
    })

    count = await _check_past_due_subscriptions()
    assert count == 1

    user = next(r for r in fake_sb.tables["users"] if r["id"] == user_id)
    assert user["plan"] == "free"
    assert user["subscription_status"] == "canceled"


async def test_grace_period_no_downgrade_within_window(monkeypatch) -> None:
    """Users within grace period are NOT downgraded."""
    fake_sb, user_id, _raw_key = _setup(monkeypatch, plan="build")

    for row in fake_sb.tables["users"]:
        if row["id"] == user_id:
            row["subscription_status"] = "past_due"

    recent_date = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    fake_sb.insert_row("subscription_events", {
        "user_id": user_id,
        "event_type": "invoice.payment_failed",
        "from_plan": "build",
        "to_plan": "build",
        "created_at": recent_date,
    })

    count = await _check_past_due_subscriptions()
    assert count == 0

    user = next(r for r in fake_sb.tables["users"] if r["id"] == user_id)
    assert user["plan"] == "build"
